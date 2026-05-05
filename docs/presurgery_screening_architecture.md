# Pre-Surgery Screening App — Architecture

## Overview

The Pre-Surgery Screening App is an external SaaS application that automates the clinical workflow for screening patients before surgery. It connects to an Electronic Health Record (EHR) system, ingests patient documents into DocRouter for AI-powered processing, extracts clinical metrics, evaluates pass/fail rules, and surfaces results to clinical staff through a structured review UI.

The system has two major components:

- **Middleware App** — a Next.js / React frontend backed by a PostgreSQL database. This is the primary interface for clinical users, integration with the EHR, and orchestration of DocRouter processing.
- **DocRouter** — the AI document processing platform. It handles document storage, OCR, classification, de-duplication, metrics extraction, and rules evaluation via flows.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    EHR System                           │
│  (patient list, documents, primary care uploads)        │
└─────────────────────┬───────────────────────────────────┘
                      │ periodic sync / on-demand upload
                      ▼
┌─────────────────────────────────────────────────────────┐
│                  Middleware App                          │
│                                                         │
│  Next.js / React Frontend                               │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Patient List │ Review │ Metrics │ Rules │ Audit │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  API Layer (Next.js API routes or dedicated service)    │
│                                                         │
│  PostgreSQL Database                                    │
│  (patients, documents, metrics, rules, audit log)       │
└─────────┬───────────────────────────┬───────────────────┘
          │ DocRouter API calls        │ DocRouter webhooks / polling
          ▼                           ▼
┌─────────────────────────────────────────────────────────┐
│                     DocRouter                           │
│                                                         │
│  Organization / Schema / Prompt management              │
│  Document storage + Textract OCR                        │
│  Flows:                                                 │
│    1. Classification flow                               │
│    2. De-duplication flow                               │
│    3. Metrics extraction flow                           │
│    4. Rules evaluation flow                             │
└─────────────────────────────────────────────────────────┘
```

---

## Processing Flow

The end-to-end flow for a patient proceeds through the following stages in order. Each stage is gated — the next stage does not start until the current one completes or is approved.

### Stage 1 — EHR Sync

1. A scheduled job (cron or manual trigger) calls the EHR API to fetch the list of patients with upcoming surgeries.
2. New patients are inserted into the Middleware `patients` table. Existing patients are updated (surgery date, status).
3. For each patient, all documents are fetched from the EHR and stored locally (or streamed directly to DocRouter).

### Stage 2 — Document Ingestion into DocRouter

1. Each document is uploaded to DocRouter via `POST /orgs/{org_id}/documents`.
2. Metadata attached to each upload:
   - `patient_id` — internal Middleware patient identifier
   - `ehr_document_id` — the source EHR document ID for round-tripping back to the EHR
   - `ehr_patient_id` — the EHR's patient identifier
   - `surgery_type` — e.g. `cardiac`, `orthopedic`
   - `document_date` — date of the document
3. The returned DocRouter `document_id` is stored in the Middleware `documents` table alongside the EHR identifiers.
4. DocRouter runs Textract OCR automatically on upload. The Middleware polls or receives a webhook when OCR is complete.

### Stage 3 — Classification Flow

A DocRouter flow (`classification_flow`) runs on each newly OCR'd document for the patient:

- Classifies the document type (e.g. lab result, discharge summary, referral letter, audit/admin record, imaging report).
- Writes the classification back as a document tag in DocRouter.
- The Middleware reads the tag and records it in the `documents.classification` column.
- Documents classified as `audit` or `admin` are flagged `excluded_from_screening = true` and do not proceed further.

### Stage 4 — De-duplication Flow

A DocRouter flow (`deduplication_flow`) runs across all non-excluded documents for the patient:

- Groups documents by type and date range.
- Uses content similarity (via LLM embedding or fingerprint) to detect near-duplicates.
- Marks duplicates in DocRouter metadata; the canonical document in each group is kept, duplicates are tagged `duplicate_of: <canonical_document_id>`.
- The Middleware reads the deduplication tags and updates `documents.duplicate_of` and `documents.is_canonical`.

### Stage 5 — First Review (Document Review)

The clinical user reviews the de-duplicated document set for the patient in the Middleware UI:

- Sees a list of canonical documents with their classification and any excluded/duplicate items.
- Can expand any document to view the PDF inline.
- Actions available:
  - **Approve document set** — proceed to metrics extraction.
  - **Request additional documents** — enter free-text note specifying what to request from which doctor. This creates an entry in `document_requests`.
  - **Upload additional documents manually** — direct upload to Middleware, which re-ingests into DocRouter and re-runs stages 2–4.
- If additional documents are requested or uploaded, the patient returns to Stage 2 and the cycle repeats until the user approves the document set.

### Stage 6 — Metrics Extraction Flow

Once the document set is approved, the Middleware triggers the DocRouter `metrics_extraction_flow`:

- All canonical documents for the patient are combined into a single logical context.
- An LLM processing flow extracts pre-surgery metrics as defined by the medical specialist for the relevant `surgery_type`. Examples:
  - Date of birth, age
  - BMI, height, weight
  - Blood pressure, heart rate
  - Blood test results (HbA1c, eGFR, INR, haemoglobin, etc.)
  - Allergies, current medications
  - ASA classification
  - Relevant comorbidities
- Each extracted metric includes:
  - The extracted value and unit
  - The source `document_id` and page number
  - The bounding box of the OCR token (from Textract output) for UI highlighting
  - A confidence score
- Results are written back to the Middleware `metrics` table via a DocRouter webhook or polling.

### Stage 7 — Rules Evaluation Flow

The Middleware triggers the DocRouter `rules_evaluation_flow`:

- Evaluates a set of pass/fail rules against the extracted metrics. Rules are defined per `surgery_type` by the medical specialist. Examples:
  - BMI < 40 → pass
  - HbA1c < 8.5% → pass
  - eGFR ≥ 30 → pass
  - INR between 0.8 and 1.2 → pass
  - No active anticoagulant therapy → pass
- Each rule result includes:
  - Pass / fail / indeterminate
  - The metric value(s) used
  - Reasoning text (LLM-generated explanation)
  - Reference to the source document and OCR token
- Results are written to the Middleware `rules` table.

### Stage 8 — Clinical Review (Metrics & Rules)

The user reviews the extracted metrics and rule results in the Middleware UI:

- Results are displayed in up to 10 tabs (one per metric/rule category) next to a PDF viewer.
- The PDF viewer highlights the relevant page and OCR bounding box for each selected metric.
- The user must acknowledge each rule result individually (pass / fail / override with justification).
- The user can:
  - **Correct a metric** — enter an override value. The corrected value is stored in `metrics.overridden_value`.
  - **Override a rule** — mark a failed rule as accepted with a mandatory free-text justification. Stored in `rules.override_justification`.
  - **Re-run analysis** — trigger the metrics extraction and rules evaluation flows again using the overridden metric values as seeds. The flow accepts overridden metrics as inputs and re-evaluates only the affected rules.
- All changes are recorded in the audit log.

### Stage 9 — Screening Decision

- If all rules pass (or have been acknowledged with override), the Middleware marks the patient as `screened`.
- If any rule has failed and not been overridden, the patient remains `pending`.
- A rejected patient can be manually marked `rejected` with a reason.

---

## Middleware UI — Pages

### 1. Patient List (`/patients`)

The primary landing page for clinical staff.

**Features:**
- Table of patients with columns: name, surgery date, surgery type, status (pending / screened / rejected), last updated, assigned reviewer.
- Sorted by surgery date ascending by default.
- Filter bar: status, surgery type, date range, assigned reviewer, search by name or EHR ID.
- Each row links to the Patient Detail page.
- Bulk actions: assign reviewer, export CSV.

**Status badges:**
- `Pending` — awaiting action at any stage
- `Screened` — all rules passed or acknowledged
- `Rejected` — manually rejected
- `Awaiting documents` — document request outstanding

### 2. Patient Detail (`/patients/[patientId]`)

Hub page for a single patient. Contains a stage progress indicator at the top and tabs for each stage.

**Tabs:**
- **Documents** — document review (Stage 5)
- **Metrics** — extracted metrics with PDF viewer (Stage 8)
- **Rules** — pass/fail rules with acknowledgement (Stage 8)
- **History** — audit trail for this patient
- **EHR** — read-only summary of EHR data (demographics, surgery details)

### 3. Document Review Tab

- List of all documents grouped by: included (canonical), excluded (audit/admin), duplicate.
- Each document shows: type, date, source, classification confidence.
- Click to open the PDF inline using DocRouter's document viewer URL.
- "Request additional documents" button opens a modal with free-text field and recipient (primary care / specialist / other).
- "Upload document" button opens a file picker; uploaded files go directly to DocRouter.
- "Approve document set" button is enabled once all documents have been reviewed.

### 4. Metrics Tab

- Split-pane layout: metrics table on the left, PDF viewer on the right.
- Metrics are grouped into categories (demographics, vitals, blood tests, medications, etc.) across up to 10 sub-tabs.
- Clicking a metric row jumps the PDF viewer to the relevant page and highlights the OCR bounding box.
- Each metric shows: name, extracted value, unit, source document, confidence, override field.
- "Re-run analysis" button triggers the flow with current overrides.

### 5. Rules Tab

- List of all rules with pass/fail badge and reasoning text.
- Each rule has an "Acknowledge" button. Failed rules require a justification text before acknowledgement.
- Overridden rules are marked with a user name and timestamp.
- Progress indicator: N of M rules acknowledged.

### 6. Audit History Tab

- Chronological log of all actions on the patient: document uploads, stage transitions, metric overrides, rule acknowledgements, status changes.
- Each entry shows: timestamp, user, action type, old value → new value.

### 7. Admin — Rule & Metric Configuration (`/admin/surgery-types/[type]`)

- Allows medical specialists to define the metric schema and rules for each surgery type.
- Stored in `surgery_type_configs` table; versioned so historical runs are reproducible.

---

## DocRouter APIs Used

All calls are scoped to the Middleware's DocRouter organization.

| Operation | DocRouter API |
|-----------|--------------|
| Upload document | `POST /orgs/{org_id}/documents` with multipart form (file + metadata tags) |
| Poll OCR status | `GET /orgs/{org_id}/documents/{doc_id}` — check `status` field |
| Download OCR output (Textract) | `GET /orgs/{org_id}/documents/{doc_id}/ocr` |
| Set document tags (classification, dedup) | `PATCH /orgs/{org_id}/documents/{doc_id}` — update `tags` |
| List documents by patient | `GET /orgs/{org_id}/documents?tag=patient_id:{id}` |
| Trigger classification flow | `POST /orgs/{org_id}/flows/{flow_id}/run` with `document_id` and `revision_snapshot` |
| Trigger deduplication flow | `POST /orgs/{org_id}/flows/{flow_id}/run` with `run_data` containing patient document IDs |
| Trigger metrics extraction flow | `POST /orgs/{org_id}/flows/{flow_id}/run` with `run_data` containing canonical document IDs and override metrics |
| Trigger rules evaluation flow | `POST /orgs/{org_id}/flows/{flow_id}/run` with `run_data` containing extracted metrics (including overrides) |
| Poll flow execution status | `GET /orgs/{org_id}/flows/{flow_id}/executions/{execution_id}` |
| Read flow execution results | `GET /orgs/{org_id}/flows/{flow_id}/executions/{execution_id}` — `run_data` field contains node outputs |
| View document PDF | DocRouter document viewer URL embedded in iframe |

---

## Postgres Database Schema

### `patients`

```sql
CREATE TABLE patients (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ehr_patient_id      TEXT NOT NULL UNIQUE,        -- EHR system's patient identifier
    full_name           TEXT NOT NULL,
    date_of_birth       DATE,
    surgery_date        TIMESTAMPTZ,
    surgery_type        TEXT,                        -- e.g. 'cardiac', 'orthopedic'
    status              TEXT NOT NULL DEFAULT 'pending',
                                                    -- pending | screened | rejected | awaiting_documents
    assigned_reviewer   UUID REFERENCES users(id),
    docrouter_org_id    TEXT NOT NULL,               -- DocRouter org this patient's docs live in
    last_ehr_sync_at    TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `documents`

```sql
CREATE TABLE documents (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id              UUID NOT NULL REFERENCES patients(id),
    ehr_document_id         TEXT,                    -- EHR source document ID (nullable for manual uploads)
    docrouter_document_id   TEXT NOT NULL UNIQUE,    -- DocRouter document_id
    document_type           TEXT,                    -- e.g. 'lab_result', 'discharge_summary'
    document_date           DATE,
    source                  TEXT,                    -- 'ehr_sync' | 'manual_upload' | 'requested'
    classification          TEXT,                    -- DocRouter classification tag
    classification_confidence NUMERIC(5,4),
    excluded_from_screening BOOLEAN NOT NULL DEFAULT false,
    exclusion_reason        TEXT,                    -- e.g. 'audit', 'admin'
    is_canonical            BOOLEAN NOT NULL DEFAULT true,
    duplicate_of            UUID REFERENCES documents(id),
    ocr_status              TEXT NOT NULL DEFAULT 'pending',
                                                    -- pending | complete | failed
    review_status           TEXT NOT NULL DEFAULT 'pending',
                                                    -- pending | approved | excluded
    reviewed_by             UUID REFERENCES users(id),
    reviewed_at             TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `document_requests`

```sql
CREATE TABLE document_requests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID NOT NULL REFERENCES patients(id),
    requested_by    UUID NOT NULL REFERENCES users(id),
    recipient       TEXT NOT NULL,                  -- 'primary_care' | 'specialist' | free text
    notes           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'open',   -- open | received | closed
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `flow_runs`

```sql
CREATE TABLE flow_runs (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id              UUID NOT NULL REFERENCES patients(id),
    flow_type               TEXT NOT NULL,
                            -- 'classification' | 'deduplication' | 'metrics_extraction' | 'rules_evaluation'
    docrouter_flow_id       TEXT NOT NULL,
    docrouter_execution_id  TEXT NOT NULL UNIQUE,
    status                  TEXT NOT NULL DEFAULT 'queued',
                            -- queued | running | complete | failed
    triggered_by            UUID REFERENCES users(id),  -- NULL for automated triggers
    started_at              TIMESTAMPTZ,
    finished_at             TIMESTAMPTZ,
    error                   TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `metrics`

One row per extracted metric per patient per flow run. Overrides create a new row with `is_override = true` referencing the original.

```sql
CREATE TABLE metrics (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id          UUID NOT NULL REFERENCES patients(id),
    flow_run_id         UUID NOT NULL REFERENCES flow_runs(id),
    surgery_type        TEXT NOT NULL,
    metric_key          TEXT NOT NULL,              -- e.g. 'bmi', 'hba1c', 'egfr'
    metric_label        TEXT NOT NULL,              -- display name
    category            TEXT NOT NULL,              -- e.g. 'vitals', 'blood_tests'
    extracted_value     TEXT,
    extracted_unit      TEXT,
    confidence          NUMERIC(5,4),
    source_document_id  UUID REFERENCES documents(id),
    source_page         INTEGER,
    ocr_bounding_box    JSONB,                      -- {left, top, width, height} in page fractions
    is_override         BOOLEAN NOT NULL DEFAULT false,
    overrides_metric_id UUID REFERENCES metrics(id),
    overridden_value    TEXT,
    overridden_by       UUID REFERENCES users(id),
    overridden_at       TIMESTAMPTZ,
    override_reason     TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `rules`

```sql
CREATE TABLE rules (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id          UUID NOT NULL REFERENCES patients(id),
    flow_run_id         UUID NOT NULL REFERENCES flow_runs(id),
    surgery_type        TEXT NOT NULL,
    rule_key            TEXT NOT NULL,              -- e.g. 'bmi_under_40', 'hba1c_controlled'
    rule_label          TEXT NOT NULL,
    category            TEXT NOT NULL,
    result              TEXT NOT NULL,              -- 'pass' | 'fail' | 'indeterminate'
    reasoning           TEXT,                       -- LLM-generated explanation
    metric_ids          UUID[],                     -- metrics used in evaluation
    acknowledged        BOOLEAN NOT NULL DEFAULT false,
    acknowledged_by     UUID REFERENCES users(id),
    acknowledged_at     TIMESTAMPTZ,
    is_override         BOOLEAN NOT NULL DEFAULT false,
    override_accepted   BOOLEAN,                    -- true = accepted despite fail
    override_justification TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `surgery_type_configs`

Versioned definitions of metrics and rules per surgery type, managed by medical specialists.

```sql
CREATE TABLE surgery_type_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    surgery_type    TEXT NOT NULL,
    version         INTEGER NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT false,
    metrics_schema  JSONB NOT NULL,                 -- array of metric definitions
    rules_schema    JSONB NOT NULL,                 -- array of rule definitions
    created_by      UUID NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (surgery_type, version)
);
```

### `audit_log`

```sql
CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID REFERENCES patients(id),
    user_id         UUID NOT NULL REFERENCES users(id),
    action          TEXT NOT NULL,
                    -- 'document_uploaded' | 'document_approved' | 'document_excluded'
                    -- | 'metric_overridden' | 'rule_acknowledged' | 'rule_overridden'
                    -- | 'status_changed' | 'flow_triggered' | 'document_requested'
    entity_type     TEXT,                           -- 'document' | 'metric' | 'rule' | 'patient'
    entity_id       UUID,
    old_value       JSONB,
    new_value       JSONB,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `users`

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL UNIQUE,
    full_name       TEXT NOT NULL,
    role            TEXT NOT NULL,                  -- 'clinician' | 'reviewer' | 'specialist' | 'admin'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## DocRouter Integration Details

### Document Metadata Tags

Every document uploaded to DocRouter carries a structured set of tags that allow the Middleware to query and correlate records:

```
patient_id:<middleware_patient_uuid>
ehr_patient_id:<ehr_patient_id>
ehr_document_id:<ehr_document_id>
surgery_type:<surgery_type>
document_date:<YYYY-MM-DD>
```

This allows DocRouter flows to receive a `patient_id` tag filter in their `run_data` and operate on the correct document set without the Middleware embedding document content in the flow invocation payload.

### Flow Design

Each DocRouter flow is designed to be stateless and re-entrant:

**Classification flow** — triggered per document. Input: `document_id`. Output: `classification` tag written back to the document.

**Deduplication flow** — triggered per patient after all documents are classified. Input: `patient_id` tag (used to look up all non-excluded documents). Output: `duplicate_of` and `is_canonical` tags written to each document.

**Metrics extraction flow** — triggered per patient after document review approval. Input: list of canonical `document_id`s, `surgery_type`, and optional `override_metrics` dict (key → value). Output: a structured JSON of metric results including `bounding_box` and `source_page` from the Textract response.

**Rules evaluation flow** — triggered after metrics extraction. Input: the metrics JSON (extracted + any overrides), `surgery_type`, and the active `surgery_type_config` version. Output: a structured JSON of rule results including `reasoning` text.

### Textract OCR Bounding Box Highlighting

When DocRouter processes a document with Textract, the OCR output includes block-level geometry (page number, bounding box in fractional coordinates). The Metrics Extraction flow, when using an LLM to locate a metric value, records the `BlockId` of the matched Textract token. The Middleware stores this as `ocr_bounding_box` in the `metrics` table. The PDF viewer in the Middleware UI reads this geometry and renders a highlight overlay at the correct position, giving the clinician direct visual confirmation of where the metric was found.

### Re-running Analysis with Overrides

When a clinician overrides a metric and requests re-analysis:

1. The Middleware assembles the current metric values, replacing extracted values with any `overridden_value` entries from the `metrics` table.
2. It calls `POST /flows/{metrics_flow_id}/run` with the override dict in `run_data`.
3. The flow seeds its LLM prompt with the overridden values, skipping re-extraction for those metrics and re-evaluating only the rules that depend on them.
4. New `metrics` and `rules` rows are inserted (linked to the new `flow_run_id`); the UI always displays the latest `flow_run_id`'s results.

---

## Key Design Decisions

**DocRouter as the document and AI layer, Middleware as the orchestration and state layer.** DocRouter owns documents, OCR, and AI processing. The Middleware owns patient state, stage gating, user actions, audit history, and business rules configuration. Neither system duplicates the other's responsibilities.

**Flows are idempotent and re-triggerable.** Each flow can be re-run safely. The Middleware always creates a new `flow_runs` row and inserts new `metrics` / `rules` rows rather than updating existing ones. The UI shows the latest run's results. This preserves full history and simplifies the re-analysis-with-overrides path.

**EHR round-trip via `ehr_document_id`.** Every document uploaded to DocRouter carries the EHR's own identifier as a tag, allowing the Middleware to write any result (e.g. screening decision, requested documents) back to the correct EHR record without ambiguity.

**Audit trail is append-only.** The `audit_log` table is never updated or deleted. Every user action — including metric overrides and rule acknowledgements — creates a new audit row recording the user, timestamp, and before/after values.

**Surgery-type-specific metric and rule schemas are versioned.** The `surgery_type_configs` table stores every version of the metric and rule definitions. Each `flow_run` implicitly records which version was active. This means historical screening decisions can always be explained in terms of the rules that were in effect at the time.
