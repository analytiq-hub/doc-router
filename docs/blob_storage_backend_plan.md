# Blob storage backend plan (move file/OCR bytes out of MongoDB)

Plan to stop storing PDF originals and OCR output as MongoDB GridFS binaries and
move them to a pluggable **filesystem or S3-compatible backend**, so a customer's
28TB disk (or any on-prem/cloud object store) can hold document bytes instead of
the Mongo data volume. Must work identically under Docker Compose (single node)
and Kubernetes (multi-replica backend).

**Related docs:**

- [On-prem installation architecture](./on_prem_installation_architecture.md) — customer-infra deployment target for this plan; §"AWS services used" currently overstates S3's role (see below) and should be corrected once this ships.
- [Flow OCR cache plan](./flow_ocr_cache_plan.md) — proposes a *new* GridFS bucket (`flow_ocr_cache`); should build directly on the `BlobStore` abstraction below instead of adding a fifth GridFS bucket.
- [Conditional OCR upload plan](./conditional_ocr_upload_plan.md) — touches the same `ocr` bucket semantics (`ocr_config_fingerprint`); no conflict, but read before touching `ocr/ocr.py`.
- [Textract polling plan](./textract_polling_plan.md) — touches `aws/textract.py`'s S3 scratch-bucket path, which stays out of scope here (see Non-goals).
- [indexes.md](./indexes.md) — new metadata collection needs an `IndexSpec` entry.

**Implementation order:** Phase 0 (abstraction, no behavior change) → Phase 1 (fs + S3 backends) → Phase 2 (backfill + dual-read) → Phase 3 (Compose/Helm deployment wiring) → Phase 4 (cutover) → Phase 5 (drop legacy GridFS collections).

---

## Goals

1. Get PDF/OCR bytes out of MongoDB's storage engine so Mongo's own disk stays small regardless of document volume — the customer's 28TB disk should hold *blobs*, not force a 28TB Mongo volume.
2. One code path where **backend choice (filesystem vs. S3-compatible) is orthogonal to orchestrator (Compose vs. Kubernetes)**. Each backend is wired to whichever orchestrator via that orchestrator's own native volume primitive — Docker bind mount/volume for Compose, PV/PVC for Kubernetes — so the same container image and application code run unmodified in both, and an operator can pick filesystem-on-local-disk in either place, not just Compose.
3. **Zero changes to callers.** Every blob read/write in the codebase already goes through one module (`ad.mongodb.blob`) — the redesign happens there, not at each call site.
4. Safe, resumable migration of existing GridFS data with no downtime and no silent data loss.
5. Preserve today's per-org data isolation and the existing `bucket:key` addressing scheme used throughout flows (`BinaryRef.storage_id = "files:{key}"` etc.).

## Non-goals

- Changing the request/response API (base64 JSON upload, multipart upload, streaming download) — those already fully materialize blobs in memory today and that behavior is unchanged here.
- Streaming/chunked I/O to reduce memory use during upload/download — real limitation (`save_blob_async`/`get_blob_async` load the whole blob into memory), but orthogonal to *where* bytes end up at rest. Worth a follow-up, not bundled in.
- Touching `aws/textract.py`'s ephemeral S3 scratch upload (`textract/tmp/{date}/{uuid}`, deleted right after the Textract job completes). That path is already S3, already transient, and unrelated to at-rest storage.
- Per-org or per-bucket backend selection. v1 is one backend for the whole deployment; call out as a future option.
- Encryption-at-rest implementation — S3 backends get SSE for free; filesystem backend relies on infra-level disk encryption (LUKS/dm-crypt), out of app scope.

---

## Current behavior (baseline)

Everything funnels through one module: `analytiq_data/mongodb/blob.py`, built directly on `motor`'s `AsyncIOMotorGridFSBucket`:

| Function | Behavior |
|---|---|
| `get_blob_async(client, bucket, key)` | Look up `db[f"{bucket}.files"]` by `filename`, open GridFS download stream by `_id`, read fully into memory. |
| `save_blob_async(client, bucket, key, blob, metadata, chunk_size_bytes=8MB)` | Delete any existing blob at `key`, then `upload_from_stream(filename=key, source=blob, metadata=metadata)`. |
| `delete_blob_async` / `delete_blobs_by_prefix_async` / `delete_flow_pins_for_flow_async` | GridFS deletes with retry/verification. |

GridFS buckets in active use today (each becomes two Mongo collections, `{bucket}.files` + `{bucket}.chunks`):

| Bucket | Written from | Shape |
|---|---|---|
| `files` | `analytiq_data/common/file.py` (`save_file_async` etc.), called from `app/routes/documents.py` upload/convert-to-PDF paths | 1–2 blobs per document (original + converted PDF) |
| `ocr` | `analytiq_data/ocr/ocr.py` (`save_ocr_json`, `save_ocr_text`) | up to N+2 blobs per document: 1 JSON payload, 1 full-text blob, N per-page text blobs |
| `flow_blobs` | `analytiq_data/flows/engine.py`, `app/routes/flows.py` | execution-scoped binaries (OCR JSON copies for trace/download, etc.) |
| `flow_pins` | `app/routes/flows.py` | pinned test-fixture binaries |

Planned addition: `flow_ocr_cache` (see `flow_ocr_cache_plan.md`) — should be built on the new abstraction, not as a fifth GridFS bucket.

No caller talks to GridFS directly except the migration file (`migrations/migration.py`, e.g. `AddGridFSFilesBucketIndexes`, `OcrPayloadTextractEnvelopeMigration`) — that's the existing precedent for a migration that iterates GridFS content directly.

**Deployment today:** no PVC and no volume mount exists for backend/worker in either Docker Compose or the Helm chart — all blob bytes physically live inside Mongo's own volume (external Atlas/DocumentDB in production, or the embedded/kind Mongo's named volume in dev). Compose already runs a separate `queue-worker` service; the Helm chart does not — it runs workers in-process inside the `backend` Deployment (`DOCROUTER_WORKERS_ENABLED=1`, `replicaCount.backend: 2`). This last point matters: **any local-disk-backed design in Kubernetes must be readable/writable from 2+ concurrently-running backend pods**, which local disk without a shared filesystem cannot do.

`on_prem_installation_architecture.md` currently lists S3 as used for "Document binaries, Textract temp uploads, exports" — only the Textract temp-upload part is real today; this plan is what makes the "document binaries" part actually true.

---

## Target design

### `BlobStore` abstraction

New subpackage `analytiq_data/storage/` with a small protocol matching the *existing* function signatures exactly, so no caller changes:

```python
class BlobStore(Protocol):
    async def get(self, bucket: str, key: str) -> dict | None: ...      # {"blob", "metadata", "upload_date"}
    async def save(self, bucket: str, key: str, blob: bytes, metadata: dict) -> None: ...
    async def delete(self, bucket: str, key: str) -> None: ...
    async def delete_by_prefix(self, bucket: str, prefix: str) -> int: ...
```

`analytiq_data/mongodb/blob.py`'s public functions become thin dispatchers to a module-level `BlobStore` instance selected at process startup. Every existing caller (`common/file.py`, `ocr/ocr.py`, `flows/engine.py`, `flows/items.py`, `flows/triggers/enqueue.py`, `worker/worker.py`, `app/routes/flows.py`) is untouched.

### Backends

1. **`GridFSBlobStore`** — today's code, moved as-is behind the protocol. Default backend for any deployment that hasn't migrated, so shipping Phase 0 is a no-op for existing installs.
2. **`FilesystemBlobStore`** — writes to `{FS_ROOT}/{bucket}/{shard}/{key}` where `shard` is a short prefix of a hash of `key` (e.g. first 4 hex chars), not `{FS_ROOT}/{bucket}/{key}` directly — see "Filesystem backend at scale" below for why. `FS_ROOT` is a single mounted directory, e.g. `/data/docrouter-blobs`, provided by whatever volume the orchestrator mounts there (Docker bind mount/volume in Compose, a PVC in Kubernetes — either works, see Deployment shapes).
3. **`S3BlobStore`** — writes to `s3://{BUCKET}/{S3_PREFIX}/{bucket}/{key}`, reusing the AWS session/credential plumbing already built in `analytiq_data/aws/aws_client.py` (same assumed-role pattern used for Textract). Works against real AWS S3 *or* any S3-compatible endpoint (MinIO, Ceph RGW) via a configurable endpoint URL.

Both new backends need a place to answer "does this key exist / list by prefix" without listing the object store on every call — reuse a single new Mongo collection for that, described next.

### Metadata sidecar collection

Replaces `{bucket}.files` (not `{bucket}.chunks` — those go away entirely). One collection, `blob_meta`, shared by both new backends:

| Field | Notes |
|---|---|
| `_id` | `{bucket}:{key}` |
| `bucket`, `key` | indexed, unique together |
| `metadata` | the existing free-form dict callers already pass in |
| `upload_date` | replaces GridFS `uploadDate` |
| `size_bytes` | |
| `backend` | `"fs"` \| `"s3"` — lets fs and s3 rows coexist during a backend switch |
| `location` | relative fs path or S3 key |

This mirrors the shape GridFS already exposed (`{bucket}.files` metadata document), so `get_blob_async`'s return shape (`{"blob", "metadata", "upload_date"}`) doesn't change for callers.

### Backend selection

One deployment-wide setting, not per-bucket or per-org in v1:

```
BLOB_STORAGE_BACKEND=gridfs|fs|s3   # default: gridfs (no behavior change for existing installs)
BLOB_STORAGE_FS_ROOT=/data/docrouter-blobs        # fs backend
BLOB_STORAGE_S3_BUCKET=...                        # s3 backend; can reuse AWS_S3_BUCKET_NAME
BLOB_STORAGE_S3_PREFIX=docrouter-blobs
BLOB_STORAGE_S3_ENDPOINT_URL=...                  # optional, for MinIO/Ceph
```

New installs are expected to set this explicitly (`fs` for a simple single-node Compose box, `s3` for Kubernetes).

---

## Deployment shapes

Backend choice (`fs` vs `s3`) and orchestrator (Compose vs Kubernetes) are independent axes — pick per-deployment, not one-per-orchestrator. Each cell below uses that orchestrator's native volume primitive to get bytes to the disk.

### Docker Compose

- **`fs` backend (the straightforward choice for a single customer box with a local 28TB disk)** — bind-mount (or named volume backed by that disk) at the same path in `backend` and `queue-worker`:

  ```yaml
  volumes:
    - /mnt/customer-28tb-disk:/data/docrouter-blobs
  ```

  Single host, single writer set — no RWX concern. Simplest, lowest-risk option, matches how the disk is physically attached.

- **`s3` backend** — add a `minio` service to `docker-compose.yml` with its own volume, point `BLOB_STORAGE_S3_ENDPOINT_URL` at it. Useful when the operator wants Compose to mirror a Kubernetes deployment's backend for testing, or already has an external S3-compatible target.

### Kubernetes

- **`fs` backend** — works the same way as Compose *if* the PVC is RWX (NFS/EFS/Longhorn/CephFS `storageClass`), because `replicaCount.backend: 2` plus in-process workers means 2+ pods need concurrent read/write access to the same bytes, and plain `ReadWriteOnce` local-disk PVs can't do that. If the customer's 28TB disk is already exported over NFS (or the cluster has an RWX-capable storage class pointed at it), this is a fully supported first-class option, not a fallback — same `FilesystemBlobStore` code as Compose, just mounted via a PVC instead of a bind mount.
- **`s3` backend** — recommended default when there's no RWX storage available, since it sidesteps the shared-filesystem requirement entirely:
  - **Self-hosted MinIO** — single-replica StatefulSet with a PVC bound to the 28TB disk (`ReadWriteOnce` is fine — only one MinIO pod touches the volume), exposed in-cluster as `minio.docrouter.svc.cluster.local:9000`. `S3BlobStore` points at it via `BLOB_STORAGE_S3_ENDPOINT_URL`. Add as an optional subchart/StatefulSet in `deploy/charts/doc-router`, gated behind `storage.backend: minio`.
  - **Real S3** (or the customer's existing S3-compatible gateway) — same `S3BlobStore` code path, no MinIO needed, just credentials.

**Bottom line for the 28TB-disk customer specifically:** if that disk can be exported as NFS to the cluster, `fs` backend + RWX PVC is the simplest match for "just use my disk." If it can only be attached to one node as local block storage, MinIO-on-PV is the way to get it usable from 2+ backend replicas without standing up NFS.

Helm changes needed (Phase 3): a `storage.backend` value (`s3-external` \| `minio` \| `filesystem`), conditional MinIO StatefulSet + PVC + Service template, conditional filesystem PVC template (documents the RWX `storageClass` requirement when `filesystem` is chosen), volumeMounts added to `backend/deployment.yaml` (and a worker Deployment, if/when one is split out of the combined backend — currently there isn't one in the Helm chart, unlike Compose).

### Filesystem backend at scale (does Docker/a 28TB volume actually work?)

Yes — a bind mount or `local`-driver named volume is just the host filesystem mounted into the container; it bypasses the container's overlay/union filesystem entirely, so **Docker imposes no size ceiling**. The constraints that actually matter are at the host-filesystem level, not the container runtime:

- **Filesystem choice**: prefer **XFS** over ext4 for this volume. ext4's inode count is fixed at `mkfs` time — with potentially tens of millions of small OCR text blobs (recall: up to N+2 blobs per document in the `ocr` bucket alone), it's possible to exhaust inodes long before exhausting space. XFS allocates inodes dynamically.
- **Directory fanout**: don't write `{bucket}/{key}` flat — millions of files in one directory degrades lookup performance on most filesystems. Use the sharded layout noted above (`{bucket}/{shard}/{key}`).
- **Backup practicality**: full-copy backup of 28TB is impractical; plan for filesystem snapshots or incremental (rsync-style) backup. This is separate from `backup_db.py`, which only backs up Mongo.
- **Docker Desktop note (not applicable to this customer's Linux server deployment, but worth stating explicitly)**: Docker Desktop's VM-disk-size limit only applies to *named volumes* stored inside the Desktop VM's virtual disk. A bind mount of a host path passes straight through to the host filesystem and isn't subject to that limit. Since production here is Docker Engine on a Linux box, this doesn't apply at all.

---

## Migration (existing GridFS data → new backend)

Cannot be a normal blocking versioned migration (`migrate.py`/pre-install Helm hook) at 28TB scale — that path holds a lock and blocks deploys. Instead:

### Phase 2a — Offline/online backfill tool

New script, same pattern as `analytiq_data/migrations/backup_db.py`: `migrate_blobs.py --bucket ocr --backend s3 ...`

- Iterate `{bucket}.files` (source of truth for what exists), stream each blob out via the existing `GridFSBlobStore.get`, write it via the target backend's `.save`, insert the `blob_meta` row.
- **Resumable**: skip any `(bucket, key)` that already has a `blob_meta` row for the target backend — safe to stop/restart.
- Does not touch or delete GridFS originals — this is a copy, not a move, until Phase 5.
- Verify byte-for-byte parity (`size_bytes` + optional sha256) between source and destination as it goes; log/report any mismatch instead of silently continuing.

### Phase 2b — Dual-read fallback (the actual cutover mechanism)

`get_blob_async` on the new backend checks `blob_meta` first; if no row exists yet for that key, falls back to a direct GridFS read (old code path, kept around unmodified). `save_blob_async` always writes to the new backend once cutover flag is flipped. This means:

- New uploads immediately land on the new backend.
- Old, not-yet-backfilled documents keep reading correctly from GridFS in the background.
- The backfill tool can run at whatever pace is safe for a 28TB corpus, with zero read-path downtime.

### Phase 2c — Cleanup migration (Phase 5)

Once the backfill reports 100% coverage (row count in `blob_meta` matches `{bucket}.files` count, per bucket) and a retention window has passed (e.g. 2 weeks, with a `backup_db.py`/mongodump snapshot taken beforehand as a safety net), add one final versioned migration following the `AddGridFSFilesBucketIndexes` precedent: drop `{bucket}.files` and `{bucket}.chunks` for all four buckets. This is the step that actually reclaims Mongo disk space — everything before it is additive/safe.

---

## Phases

1. **Phase 0 — Abstraction, no behavior change.** `BlobStore` protocol, `GridFSBlobStore` wrapping today's code verbatim, `blob_meta` collection schema defined (unused), `BLOB_STORAGE_BACKEND` config defaulting to `gridfs`. Ship this alone first; it's a refactor with an identical test surface.
2. **Phase 1 — New backends.** `FilesystemBlobStore`, `S3BlobStore`, unit tests (round-trip save/get/delete/delete_by_prefix per backend), wire `fs` backend into Compose for local/dev testing.
3. **Phase 2 — Backfill + dual-read.** `migrate_blobs.py`, dual-read fallback in `get_blob_async`, parity verification, run against a staging copy first.
4. **Phase 3 — Deployment wiring.** Helm `storage.backend` value + MinIO/filesystem PVC templates, Compose volume docs, update `on_prem_installation_architecture.md` to reflect real S3 usage.
5. **Phase 4 — Cutover.** New installs default to `s3`/`minio`; existing installs run backfill in production, verify coverage, flip `BLOB_STORAGE_BACKEND`, monitor error rates and latency.
6. **Phase 5 — Cleanup migration.** Drop legacy `{bucket}.files`/`{bucket}.chunks` collections once coverage + retention window are confirmed.

---

## Test plan

| Test | Assert |
|---|---|
| Backend round-trip (fs, s3, gridfs) | save → get → delete → get returns `None`, for each backend independently |
| `delete_by_prefix` | matches today's `flow_blobs`/`flow_pins` prefix-delete semantics on new backends |
| Dual-read fallback | key present only in GridFS still reads correctly through new backend's `get` |
| Backfill resumability | interrupt mid-run, restart, verify no duplicate work and full coverage |
| Backfill parity | byte-for-byte (size + hash) match between source GridFS blob and migrated blob |
| Coverage check | `blob_meta` row count == `{bucket}.files` row count per bucket before Phase 5 runs |
| Compose smoke test | upload → OCR → download round-trip with `fs` backend and a real bind mount |
| Kubernetes smoke test | same round-trip against MinIO-backed `s3` backend with `replicaCount.backend: 2` |
| Org isolation | unchanged — bucket/key namespacing carries over identically to new backends |

---

## Open questions

1. **Is the customer's 28TB disk a single node's local disk, or exportable as NFS?** If it's NFS-exportable (or the cluster already has an RWX storage class), `fs` backend + RWX PVC is the simplest match in Kubernetes too. If it's node-local block storage only, MinIO-on-PV is the path that works without standing up NFS. Compose is unaffected either way (single host, bind mount just works).
2. **Backend granularity** — v1 is one global backend. If a customer later needs per-org region pinning (e.g. data residency), that's a `blob_meta`/config extension, not a redesign, since `backend` is already a per-row field.
3. **Should Textract's ephemeral S3 scratch path (`aws/textract.py`) be unified onto `S3BlobStore`'s session/config?** Out of scope per Non-goals above, but worth revisiting once `S3BlobStore` exists, since it would consolidate two separate S3 client setups into one.

---

## Summary

All blob I/O already funnels through one module (`analytiq_data/mongodb/blob.py`), which makes this a contained refactor: introduce a `BlobStore` protocol behind it, add `Filesystem` and `S3` implementations, and migrate existing GridFS data via a resumable backfill tool with a dual-read fallback — no caller in the codebase needs to change. Backend choice (filesystem or S3-compatible) is independent of orchestrator: Docker Compose can bind-mount local disk directly or point at a MinIO container; Kubernetes can mount an RWX PVC onto that same filesystem backend or use MinIO/real S3 when only node-local block storage is available (needed because `replicaCount.backend: 2` means multiple pods share the data). A 28TB volume is not a Docker limitation — bind mounts bypass the container filesystem entirely — but does call for XFS (dynamic inodes) and a sharded key layout instead of a flat directory. A final cleanup migration drops the legacy GridFS collections once the backfill is verified complete, which is the step that actually shrinks Mongo's own storage footprint.
