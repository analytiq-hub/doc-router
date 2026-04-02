# MongoDB Community Edition on Fedora (doc-router)

This document describes how we run **MongoDB Community Edition** on **Fedora** for local development and testing, including the **mongot** sidecar used for **Atlas Search** features on self-hosted MongoDB (for example **`$vectorSearch`** and **`$search`** used by knowledge bases).

It complements [INSTALL.local_devel.md](INSTALL.local_devel.md) and the `MONGODB_URI` notes in [env.md](env.md).

---

## What we run

| Component | Role |
|-----------|------|
| **`mongod`** | Data server (`mongod` / `mongod-community.service`), default port **27017**. |
| **Replica set** | A single-node replica set (for example name **`rs0`**) is typical for local dev; it matches how PyMongo and tools connect and is compatible with mongot replication. |
| **mongot** | Separate process (**`mongot-community.service`**) that implements search indexes for `createSearchIndexes` / `$vectorSearch` / `$search` when using MongoDB 8.x self-hosted with community mongot. |

Connection strings often use:

```text
mongodb://localhost:27017/?directConnection=true
```

`directConnection=true` avoids the driver trying to discover other replica set members when only one node exists.

---

## 1. Install MongoDB Community Edition on Fedora

MongoDB publishes **`.repo`** files for RHEL-compatible systems; Fedora is close enough that the **current** MongoDB instructions for [Install on Red Hat](https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-redhat/) apply with small adjustments.

### 1.1 Add the MongoDB package repository

Create a repo file (exact filename and URL should match the MongoDB version you want, for example **8.0**):

```bash
sudo tee /etc/yum.repos.d/mongodb-org-8.0.repo <<'EOF'
[mongodb-org-8.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/8/mongodb-org/8.0/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://pgp.mongodb.com/server-8.0.asc
EOF
```

Pick the **baseurl** that matches your **MongoDB major** and **architecture** (`x86_64` vs `aarch64`). If `dnf` reports a mismatch, use the URL from the official tutorial for your version.

### 1.2 Install packages

```bash
sudo dnf install -y mongodb-org mongodb-org-server mongodb-org-mongos mongodb-org-database-tools mongodb-mongosh
```

For a **minimal** server install, `mongodb-org-server` and `mongosh` may be enough; the meta-package **`mongodb-org`** pulls the usual set.

### 1.3 Firewall (if enabled)

If clients are not only on localhost:

```bash
sudo firewall-cmd --permanent --add-port=27017/tcp
sudo firewall-cmd --reload
```

---

## 2. Configure `mongod`

Main config file: **`/etc/mongod.conf`** (path may vary slightly by package; check `rpm -ql mongodb-org-server`).

Typical areas to set explicitly:

- **`net.bindIp`**: for local-only dev, `127.0.0.1` is fine; for LAN access, include the host IP or `0.0.0.0` (with firewall rules).
- **`storage.dbPath`**: default is often `/var/lib/mongo`.
- **`replication.replSetName`**: set to the name you will use when initiating the replica set (for example **`rs0`**).

Example snippet (YAML):

```yaml
storage:
  dbPath: /var/lib/mongo

net:
  port: 27017
  bindIp: 127.0.0.1

replication:
  replSetName: rs0

systemLog:
  destination: file
  path: /var/log/mongodb/mongod.log
  logAppend: true
```

### WiredTiger cache (RAM)

MongoDB’s **WiredTiger** cache defaults to a fraction of RAM. To **cap** memory used by `mongod`, set something like:

```yaml
storage:
  wiredTiger:
    engineConfig:
      cacheSizeGB: 2
```

Adjust to your machine; this is one of the main levers for **limiting mongod RAM** without involving systemd.

After edits:

```bash
sudo systemctl restart mongod
# or on some installs:
sudo systemctl restart mongod-community
```

Use `systemctl status` to confirm the exact unit name on your system (`mongod` vs `mongod-community`).

---

## 3. Initialize the replica set

Start the server, then use **`mongosh`**:

```bash
sudo systemctl enable --now mongod   # or mongod-community

mongosh --eval 'rs.initiate({ _id: "rs0", members: [{ _id: 0, host: "localhost:27017" }] })'
```

Wait until `rs.status()` shows a **PRIMARY** for the member.

---

## 4. Mongot (vector / Atlas Search on self-hosted)

For **Knowledge Base** vector search in this project, the server must support **`createSearchIndexes`** and **`$vectorSearch`**. On **self-hosted MongoDB 8.2+**, that is provided by the **mongot** process (often packaged or installed separately from the core `mongod` RPM).

### 4.1 Install and configure mongot

Follow the **current MongoDB documentation** for **Community mongot** (install path, config file location, and systemd unit name can change by release). On our setups we run a **`mongot-community.service`** that:

- Points at the same **`localhost:27017`** sync source.
- Uses a **config file** (for example `config.yml` in mongot’s working directory).
- Logs to **journald** (see below).

### 4.2 Mongot user

Mongot typically connects with a **dedicated user** (logs often show something like `mongotUser` on `admin`). Create that user in MongoDB per the mongot install guide and grant the roles it requires.

### 4.3 Start order

1. **`mongod`** must be running and PRIMARY.
2. Then start **`mongot-community`** (or the unit name your package installed).

```bash
sudo systemctl enable --now mongot-community
sudo systemctl status mongot-community
```

---

## 5. Systemd services (how we run things)

Enable both services to start on boot:

```bash
sudo systemctl enable mongod          # or mongod-community
sudo systemctl enable mongot-community
```

Check they are active:

```bash
systemctl is-active mongod mongot-community
```

### Limit CPU and RAM with systemd

Use **drop-in overrides** so upgrades to the unit file do not wipe your limits.

**Example:** cap mongot Java heap indirectly via environment, and cap CPU/RAM via cgroup limits.

```bash
sudo systemctl edit mongot-community
```

Example override (adjust paths and variable names to match your mongot unit):

```ini
[Service]
MemoryMax=4G
CPUQuota=200%
Environment=JAVA_TOOL_OPTIONS=-Xmx2g
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart mongot-community
```

For **`mongod`**, prefer **`storage.wiredTiger.engineConfig.cacheSizeGB`** for RAM; you can still use **`MemoryMax=`** in systemd as a hard ceiling if needed.

Verify:

```bash
systemctl show mongot-community -p MemoryMax -p CPUQuotaProportion
```

---

## 6. Application configuration (doc-router)

In the project root **`.env`**:

```bash
MONGODB_URI=mongodb://localhost:27017/?directConnection=true
```

The app and tests use this URI; pytest may set `ENV=pytest_*` per worker—those are **logical database names** inside the same `mongod`, not separate servers.

---

## 7. Upgrading MongoDB and mongot

1. **Back up** (see [Backup](#9-backup) below).
2. Read the **release notes** for your target **minor** (8.x) for incompatible changes.
3. **Upgrade packages**:

   ```bash
   sudo dnf upgrade mongodb-org '*'
   ```

4. Restart **`mongod`**, then **`mongot-community`**:

   ```bash
   sudo systemctl restart mongod
   sudo systemctl restart mongot-community
   ```

5. Smoke-test: `mongosh` connect, `rs.status()`, and a small **`createSearchIndexes`** / **`$vectorSearch`** against a test collection.

---

## 8. Logs and what to watch for

### 8.1 Where logs go

| Component | Typical log source |
|-----------|-------------------|
| **mongod** | File: `/var/log/mongodb/mongod.log` (if configured), and/or **journald**: `journalctl -u mongod` |
| **mongot** | **journald**: `journalctl -u mongot-community` |

Follow live:

```bash
journalctl -u mongod -f
journalctl -u mongot-community -f --since "now"
```

Mongot may also write **FTDC / diagnostic** data under something like **`/var/lib/mongot/`** (see mongot logs for the exact path).

### 8.2 Messages that are usually normal

- **Initial sync / `Enqueueing initial sync` / `Queued initial syncs`**: mongot is building Lucene indexes for new search indexes.
- **`Collection was dropped` / `SteadyStateException` / “closing change stream”** after a drop: expected when databases or collections are removed; mongot tears down indexes for that namespace.
- **`No index in catalog` (WARN)** right after **`createSearchIndexes`**: short race before mongot registers the index; the application retries readiness where implemented. If it persists, the index may not have been created or mongot is overloaded.

### 8.3 Problems we have actually hit

| Symptom | Likely cause | Mitigation |
|---------|----------------|------------|
| **`java.lang.OutOfMemoryError: Java heap space`** in mongot | Too many indexes / initial sync backlog / heap too small | Increase **`JAVA_TOOL_OPTIONS=-Xmx...`**, raise **`MemoryMax`**, reduce parallel test load, or give the host more RAM. |
| **`No index in catalog`** (mongot WARN) | Query before index is registered | Wait after index creation (app uses a readiness probe), retry searches, avoid hammering mongot during mass index creation. |
| **High CPU / long `numQueued` initial syncs** | Many collections / parallel workers creating indexes | Limit concurrency, cap systemd CPU/RAM, or use a dedicated dev instance. |

---

## 9. Backup

### 9.1 Filesystem backup of `dbPath`

Stop writes or use filesystem snapshots consistently with MongoDB documentation for your storage. Not always ideal for fast iteration.

### 9.2 `mongodump` / `mongorestore`

Logical backup (good for moving a database between hosts):

```bash
mongodump --uri="mongodb://localhost:27017/?directConnection=true" --db=yourdb --out=/backup/mongodump-$(date +%F)
mongorestore --uri="mongodb://localhost:27017/?directConnection=true" /backup/mongodump-YYYY-MM-DD/yourdb
```

### 9.3 Project helper

The repo includes migration tooling under `packages/python/analytiq_data/migrations/` (see **MIGRATIONS.md** and **`backup_db.py`**). Use those for copying between URIs/databases when aligning with how this project expects data.

---

## 10. Cleanup: databases, collections, and mongot

### 10.1 Drop a database (application data)

From **`mongosh`**:

```javascript
use yourdb
db.dropDatabase()
```

Dropping the database removes **collections** and **data**. Mongot learns via the oplog/change streams and will **tear down** search indexes tied to those namespaces (you may see drop-related lines in **`journalctl -u mongot-community`**).

### 10.2 Drop search indexes only

If you need to remove Atlas Search indexes without dropping the whole collection, use the appropriate **`dropSearchIndexes`** / admin commands for your MongoDB version (see MongoDB docs). Mongot will stop maintaining those indexes.

### 10.3 Test databases (`pytest_*`)

When running pytest, the suite typically uses per-worker database names like **`pytest_gw0`**. You can list and drop leftover DBs:

```javascript
show dbs
// then for each name:
use pytest_gw0
db.dropDatabase()
```

### 10.4 Mongot on-disk state

After large index churn, mongot’s on-disk directories may not shrink immediately. If you **fully** decommission mongot (only in a dev VM), you might:

1. Stop **`mongot-community`**.
2. Remove mongot state **only** as documented for your mongot version (often under **`/var/lib/mongot/`** or similar—confirm before `rm -rf`).
3. Start mongot again and let it rebuild from MongoDB metadata.

Do **not** delete mongot’s data directory while production traffic depends on it without following MongoDB’s procedures.

---

## 11. Quick health checklist

- [ ] `mongosh "mongodb://localhost:27017/?directConnection=true"` connects.
- [ ] `rs.status()` shows PRIMARY (if using a replica set).
- [ ] `systemctl is-active mongod mongot-community` → `active`.
- [ ] Create a test collection, **`createSearchIndexes`**, then a minimal **`$vectorSearch`** (or run the project’s mongot integration test).
- [ ] `journalctl -u mongot-community -n 50` shows no repeated OOM / fatal errors after load.

---

## References

- [MongoDB: Install on Red Hat / CentOS](https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-redhat/)
- [MongoDB: mongod configuration](https://www.mongodb.com/docs/manual/reference/configuration-options/)
- Project: [INSTALL.local_devel.md](INSTALL.local_devel.md), [env.md](env.md), `deploy/compose/docker-compose.embedded.yml` (Atlas Local / mongot in Docker alternative).
