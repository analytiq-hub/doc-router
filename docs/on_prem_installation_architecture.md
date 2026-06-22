# On-Prem Installation Architecture

This document describes how to deploy DocRouter on customer-owned infrastructure (Docker Compose or Kubernetes) and which external cloud services it depends on. It focuses on AWS account setup, IAM roles and permissions, LLM provider configuration, and Vertex AI Gemini.

---

## Overview

DocRouter is a multi-service application that runs on your servers but calls out to managed cloud APIs for document OCR, object storage, email, and LLM inference.

**Diagram:** [on_prem_installation_architecture.excalidraw](on_prem_installation_architecture.excalidraw) — open in [Excalidraw](https://excalidraw.com) (File → Open) or the VS Code Excalidraw extension.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Customer infrastructure                         │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐     │
│  │ Next.js  │  │ FastAPI  │  │ Worker   │  │ MongoDB          │     │
│  │ frontend │  │ backend  │  │ (queue)  │  │ (local or Atlas) │     │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────────────┘     │
│       │             │             │                                 │
│       └─────────────┴─────────────┘                                 │
│                     │                                               │
└─────────────────────┼───────────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┬──────────────────┐
        ▼             ▼             ▼                  ▼
   ┌─────────┐  ┌──────────┐  ┌──────────┐    ┌───────────────┐
   │ AWS     │  │ AWS      │  │ AWS      │    │ LLM APIs      │
   │ S3      │  │ Textract │  │ SES      │    │ OpenAI,       │
   │         │  │          │  │          │    │ Mistral,      │
   └─────────┘  └──────────┘  └──────────┘    │ Gemini,       │
        │             │             │         │ Vertex AI,    │
        │             │             │         │ Bedrock, …    │
        └─────────────┴─────────────┘         └───────────────┘
```

**Typical on-prem stack**


| Component            | Where it runs                          | Notes                                             |
| -------------------- | -------------------------------------- | ------------------------------------------------- |
| Frontend (Next.js)   | Customer VM / container                | Port 3000                                         |
| Backend (FastAPI)    | Customer VM / container                | Port 8000                                         |
| Worker               | Customer VM / container                | Required for queue-based OCR and flows            |
| MongoDB              | Customer VM, Atlas, or embedded Docker | All app state and encrypted credentials           |
| AWS                  | Customer AWS account                   | S3, Textract, SES; optional Bedrock               |
| GCP                  | Customer GCP project                   | Optional; Vertex AI Gemini and Mistral Vertex OCR |
| Third-party LLM APIs | Vendor SaaS                            | OpenAI, Anthropic, Mistral, Gemini API, etc.      |


Credentials are stored encrypted in MongoDB (`cloud_config` for deployment-wide AWS/GCP/Azure; `llm_providers` for per-provider API keys). On first startup, values from `.env` are seeded into the database when admin bootstrap completes.

---

## Step 1 — Create an AWS account

1. Go to [https://aws.amazon.com](https://aws.amazon.com) and create an account (or use an existing organizational account).
2. Enable MFA on the root user; do **not** use root credentials for DocRouter.
3. Create an IAM admin user (or use AWS IAM Identity Center) for console and Terraform work.
4. Choose a primary region. DocRouter defaults to `**us-east-1`** for AWS clients (S3, Textract, SES, Bedrock). Keep S3, Textract, and SES in the same region when possible.
5. (Recommended) Enable AWS CloudTrail in the account for audit and troubleshooting.

---

## Step 2 — Provision AWS resources

You can provision infrastructure manually (console) or with the reference Terraform in the [analytiq-terraform](https://github.com/analytiq-hub/analytiq-terraform) sandbox ([applications/docrouter](https://github.com/analytiq-hub/analytiq-terraform/tree/main/applications/docrouter)), which wraps [modules/docrouter](https://github.com/analytiq-hub/analytiq-terraform/tree/main/modules/docrouter).

### Option A — Terraform (recommended)

Clone the sandbox and apply from the DocRouter application module:

```bash
git clone https://github.com/analytiq-hub/analytiq-terraform.git
cd analytiq-terraform/applications/docrouter
terraform init
terraform apply -var='prefix=docrouter' -var='bucket_name=your-company-docrouter-data'
```

Capture outputs:


| Output           | Use in DocRouter                      |
| ---------------- | ------------------------------------- |
| `app_access_key` | `AWS_ACCESS_KEY_ID`                   |
| `app_secret_key` | `AWS_SECRET_ACCESS_KEY`               |
| `bucket_name`    | `AWS_S3_BUCKET_NAME`                  |
| `app_role_arn`   | Verify role exists (see naming below) |


### Option B — Manual console setup

Follow the IAM layout below so it matches what the application expects.

---

## Step 3 — IAM roles, users, and permissions

The reference Terraform module (modules/docrouter]([https://github.com/analytiq-hub/analytiq-terraform/tree/main/modules/docrouter](https://github.com/analytiq-hub/analytiq-terraform/tree/main/modules/docrouter)) in [analytiq-terraform](https://github.com/analytiq-hub/analytiq-terraform)) creates a **user + role** pattern. DocRouter authenticates with the IAM **user** access keys, then **assumes an IAM role** for S3 and Textract. Bedrock is invoked with the **user** credentials directly (not the assumed role).

### Naming convention (required)

The backend derives the role ARN from the IAM user name:

- IAM user: `{prefix}-app-user` (e.g. `docrouter-app-user`)
- IAM role: `{prefix}-app-role` (e.g. `docrouter-app-role`)

If the user name does not follow `{prefix}-{suffix}-user`, role assumption fails and Textract/S3 will not work. Use the Terraform module or mirror its names exactly.

### Resources created by Terraform


| Resource   | Name pattern           | Purpose                                     |
| ---------- | ---------------------- | ------------------------------------------- |
| IAM user   | `{prefix}-app-user`    | Long-lived access keys in `.env` / admin UI |
| IAM role   | `{prefix}-app-role`    | Assumed for S3 and Textract                 |
| S3 bucket  | `bucket_name` variable | Document storage and Textract staging       |
| Access key | (attached to user)     | Programmatic access                         |


### Permissions on the IAM role (`{prefix}-app-role`)


| Permission source                           | AWS service     | What DocRouter uses it for                                                          |
| ------------------------------------------- | --------------- | ----------------------------------------------------------------------------------- |
| Managed policy `AmazonTextractFullAccess`   | Amazon Textract | OCR on uploaded PDFs and images                                                     |
| Managed policy `AmazonSESFullAccess`        | Amazon SES      | Invitation, verification, and notification email                                    |
| Inline policy `{prefix}-app-role-s3-access` | Amazon S3       | `GetObject`, `PutObject`, `ListBucket`, `DeleteObject` on the DocRouter bucket only |


S3 bucket settings from Terraform:

- Server-side encryption: AES-256
- Bucket policy grants the app role `s3:`* on bucket objects

### Permissions on the IAM user (`{prefix}-app-user`)


| Policy                                | Actions                                                           | Why on the user (not the role)                            |
| ------------------------------------- | ----------------------------------------------------------------- | --------------------------------------------------------- |
| Inline `assume-{prefix}-app-role`     | `sts:AssumeRole` on `{prefix}-app-role`                           | Allows the app to assume the role for S3/Textract         |
| Inline `{prefix}-bedrock-user-policy` | `bedrock:InvokeModel` on foundation models and inference profiles | Bedrock auth uses user keys, not assumed-role credentials |


Bedrock policy (from Terraform):

```json
{
  "Effect": "Allow",
  "Action": "bedrock:InvokeModel",
  "Resource": [
    "arn:aws:bedrock:*::foundation-model/*",
    "arn:aws:bedrock:*:*:inference-profile/*"
  ]
}
```

### Minimal manual IAM policy (if not using managed policies)

For least-privilege manual setup, attach equivalent permissions to the **role**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::YOUR-BUCKET-NAME",
        "arn:aws:s3:::YOUR-BUCKET-NAME/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "textract:StartDocumentAnalysis",
        "textract:GetDocumentAnalysis",
        "textract:StartDocumentTextDetection",
        "textract:GetDocumentTextDetection"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail",
        "ses:SendRawEmail"
      ],
      "Resource": "*"
    }
  ]
}
```

On the **user**, add `sts:AssumeRole` for the role ARN and `bedrock:InvokeModel` if you use Bedrock.

---

## Step 4 — AWS services used by DocRouter


| Service             | Required?                            | Used for                                                                    |
| ------------------- | ------------------------------------ | --------------------------------------------------------------------------- |
| **Amazon S3**       | Yes (for default OCR pipeline)       | Document binaries, Textract temp uploads, exports                           |
| **Amazon Textract** | Yes (unless org OCR mode is changed) | Default OCR engine (`textract` mode)                                        |
| **Amazon SES**      | Optional                             | Outbound email when `SES_FROM_EMAIL` is set; sender must be verified in SES |
| **Amazon Bedrock**  | Optional                             | Claude and embedding models via `bedrock` LLM provider                      |
| **AWS STS**         | Yes (with role pattern)              | `AssumeRole` from user to role                                              |


DocRouter does **not** require AWS Lambda, ECS, or EKS for on-prem installs; only the APIs above.

### Bedrock model access

After IAM is in place, open the **Amazon Bedrock** console → **Model access** (or **Foundation models**) and enable the models you plan to use, for example:

- `us.anthropic.claude-sonnet-4-6`
- `us.anthropic.claude-opus-4-6-v1`
- `cohere.embed-v4:0`
- `amazon.titan-embed-text-v2:0`

Then enable the **Bedrock** provider in DocRouter (see LLM section below).

### SES setup

1. Verify the sender address or domain in SES.
2. If the account is in the SES sandbox, verify recipient addresses or request production access.
3. Set `SES_FROM_EMAIL` in `.env` to the verified sender.

---

## Step 5 — Configure AWS in DocRouter

### Via `.env` (first boot)

Add to the project root `.env` (see `.env.example.aws_lightsail`):

```bash
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_BUCKET_NAME=your-company-docrouter-data
SES_FROM_EMAIL=noreply@yourdomain.com   # optional
```

On startup, after the admin user exists, these values are encrypted and stored in `cloud_config` (`type: "aws"`).

### Via admin UI (ongoing)

**Account → Development → AWS setup** (`/settings/account/development/aws-config`)

Stores access key ID, secret access key, and S3 bucket name in `cloud_config`. This overrides `.env` for runtime behavior.

### Verify

Check backend logs after restart:

- Success: AWS clients initialize and Textract runs on document upload
- Failure: `AWS credentials are not correct` or `AWS role assumption failed` — usually wrong keys, missing `AssumeRole`, or user/role naming mismatch

---

## Step 6 — LLM providers and API keys

DocRouter routes all LLM calls through [LiteLLM](https://github.com/BerriAI/litellm). Providers are defined in code (`packages/python/analytiq_data/llm/providers.py`), seeded into MongoDB on startup, and configured per deployment.

### Supported providers (summary)


| Provider               | Auth                     | Env variable                                                                  | Default enabled |
| ---------------------- | ------------------------ | ----------------------------------------------------------------------------- | --------------- |
| OpenAI                 | API key                  | `OPENAI_API_KEY`                                                              | Yes             |
| Anthropic              | API key                  | `ANTHROPIC_API_KEY`                                                           | Yes             |
| Gemini (Google AI API) | API key                  | `GEMINI_API_KEY`                                                              | Yes             |
| Mistral                | API key                  | `MISTRAL_API_KEY`                                                             | Yes             |
| Groq                   | API key                  | `GROQ_API_KEY`                                                                | Yes             |
| xAI                    | API key                  | `XAI_API_KEY`                                                                 | Yes             |
| OpenRouter             | API key                  | `OPENROUTER_API_KEY`                                                          | Yes             |
| Azure OpenAI           | API key                  | `AZURE_OPENAI_API_KEY`                                                        | No              |
| Microsoft Foundry      | Service principal        | `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_API_BASE` | No              |
| AWS Bedrock            | AWS user keys            | (same as AWS above)                                                           | No              |
| Google Vertex AI       | GCP service account JSON | GCP setup UI                                                                  | No              |


### How to add API keys

**Option 1 — `.env` at install time**

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
MISTRAL_API_KEY=...
GEMINI_API_KEY=...
GROQ_API_KEY=...
```

On first startup, `setup_llm_providers` copies non-empty env values into encrypted `llm_providers.token` fields.

**Option 2 — Admin UI (preferred after install)**

1. Sign in as admin.
2. Go to **Account → Development → LLM Manager** (`/settings/account/development/llm-manager`).
3. Open a provider (e.g. OpenAI, Mistral).
4. Paste the API key, enable the provider, and select which models are enabled.
5. Use **Test** on a model to confirm connectivity.

API: `PUT /v0/account/llm/provider/{provider_name}` with `{ "token": "...", "enabled": true, ... }`.

**Bedrock** — no separate API key; enable the provider and ensure AWS user has `bedrock:InvokeModel` and models are enabled in the Bedrock console.

**Vertex AI** — do not set a token on the LLM provider; use GCP setup (next section).

### Recommended models for document extraction

For speed and cost on production document workflows:


| Use case                 | Recommended model               | Provider                 |
| ------------------------ | ------------------------------- | ------------------------ |
| Document processing      | `gemini/gemini-3-flash-preview` | Vertex AI or Gemini API  |
| Document Agent           | `claude-opus-4-6`               | AWS Bedrock or Anthropic |
| Chat With Knowledge Base | openai-5.2                      | OpenAI                   |


See [knowledge_base/prompts.md](knowledge_base/prompts.md) for model-selection guidance used by built-in agents.

---

## Step 7 — Enable Vertex AI Gemini

Vertex AI is the recommended path when you want Gemini in a **GCP project** (enterprise billing, VPC-SC, data residency) rather than the consumer **Gemini API** (`GEMINI_API_KEY`).

Vertex also unlocks **Mistral Vertex OCR** (`mistral_vertex` OCR mode), which uses the same GCP service account.

### 7.1 Create a GCP project

1. Open [Google Cloud Console](https://console.cloud.google.com).
2. Create a project (note the **Project ID**).
3. Enable billing on the project.

### 7.2 Enable APIs

In **APIs & Services → Enable APIs**, enable:

- **Vertex AI API** (`aiplatform.googleapis.com`)

For Mistral Vertex OCR only, no extra publisher API is required beyond Vertex AI and Cloud Platform scope.

### 7.3 Create a service account

1. **IAM & Admin → Service Accounts → Create**.
2. Name example: `docrouter-vertex`.
3. Grant roles (minimum practical set):
  - **Vertex AI User** (`roles/aiplatform.user`)
4. Create a **JSON key** and download it securely.

### 7.4 Configure DocRouter

**Option A — Admin UI**

1. **Account → Development → GCP setup** (`/settings/account/development/gcp-config`).
2. Paste the full service account JSON.
3. Save.

**Option B — Environment (legacy / automation)**

Some deployments set `GOOGLE_APPLICATION_CREDENTIALS` to a JSON file path on the server. The primary supported path for on-prem is the GCP setup UI, which stores encrypted JSON in `cloud_config` (`type: "gcp"`).

**Optional — region**

Set in `.env`:

```bash
VERTEX_AI_LOCATION=global
```

Default is `global`. LiteLLM uses this as `vertex_location` with `vertex_project` from the service account `project_id`. For Mistral Vertex OCR, the Mistral endpoint is fixed to `us-central1` in code.

### 7.5 Enable Vertex models in LLM Manager

1. **Account → Development → LLM Manager → Google Vertex AI**.
2. Enable the provider.
3. Enable models, for example:
  - `vertex_ai/gemini-2.5-flash` — strong quality/latency balance for extraction
  - `vertex_ai/gemini-3.1-flash-lite-preview` — newer flash tier
  - `vertex_ai/gemini-embedding-001` — embeddings for knowledge bases
4. Run **Test** on `vertex_ai/gemini-2.5-flash`.

### Gemini API vs Vertex AI


|              | Gemini API (`GEMINI_API_KEY`)   | Vertex AI (GCP service account)     |
| ------------ | ------------------------------- | ----------------------------------- |
| Setup        | API key from Google AI Studio   | GCP project + service account JSON  |
| Model prefix | `gemini/gemini-3-flash-preview` | `vertex_ai/gemini-2.5-flash`        |
| Best for     | Quick start, dev                | Enterprise GCP, Mistral Vertex OCR  |
| DocRouter UI | LLM Manager → Gemini            | GCP setup + LLM Manager → Vertex AI |


For the best **quality/performance** combo on Vertex, start with `**vertex_ai/gemini-2.5-flash`**; move to `**vertex_ai/gemini-3.1-flash-lite-preview`** when you want the newest flash generation.

---

## Step 8 — End-to-end checklist after AWS account creation

Use this ordered checklist for a typical on-prem deployment.

### AWS

- [ ] Create S3 bucket (encrypted, private, correct region)
- [ ] Create IAM role `{prefix}-app-role` with Textract, SES, and S3 bucket access
- [ ] Create IAM user `{prefix}-app-user` with access key
- [ ] Grant user `sts:AssumeRole` on the role
- [ ] Grant user `bedrock:InvokeModel` if using Bedrock
- [ ] (Optional) Verify SES sender and set `SES_FROM_EMAIL`
- [ ] (Optional) Enable Bedrock foundation models in the console
- [ ] Put `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_BUCKET_NAME` in `.env` or AWS setup UI

### Application platform

- [ ] Provision server or containers
- [ ] Install MongoDB and set `MONGODB_URI`
- [ ] Set `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `NEXTAUTH_SECRET`, `NEXTAUTH_URL`
- [ ] Deploy frontend, backend, worker, and reverse proxy (nginx)
- [ ] Confirm migrations ran and admin can log in

### LLM

- [ ] Add API keys via `.env` or **LLM Manager** (OpenAI, Mistral, etc.)
- [ ] Enable chosen models per organization prompts and flows
- [ ] (Optional) Enable Bedrock provider after AWS + model access
- [ ] (Optional) Complete GCP Vertex setup and enable `vertex_ai/gemini-2.5-flash`

### Validation

- [ ] Upload a PDF; confirm Textract OCR completes
- [ ] Run a prompt against your chosen flash model
- [ ] Send a test email if using SES
- [ ] (Optional) Test Bedrock or Vertex from LLM Manager

---

## Credential storage reference


| Credential            | Storage                           | Admin UI                            |
| --------------------- | --------------------------------- | ----------------------------------- |
| AWS keys + bucket     | `cloud_config` `type: "aws"`      | Account → Development → AWS setup   |
| GCP service account   | `cloud_config` `type: "gcp"`      | Account → Development → GCP setup   |
| Azure Foundry SP      | `cloud_config` `type: "azure"`    | Account → Development → Azure setup |
| OpenAI, Mistral, etc. | `llm_providers.token` (encrypted) | Account → Development → LLM Manager |


---

## Related Terraform sandbox

The canonical IAM and S3 layout lives in the [analytiq-terraform](https://github.com/analytiq-hub/analytiq-terraform) GitHub sandbox:

- [applications/docrouter/main.tf](https://github.com/analytiq-hub/analytiq-terraform/blob/main/applications/docrouter/main.tf) — application entrypoint
- [modules/docrouter/main.tf](https://github.com/analytiq-hub/analytiq-terraform/blob/main/modules/docrouter/main.tf) — IAM user, role, policies, S3 bucket

When in doubt, clone the sandbox, run `terraform apply` from `applications/docrouter`, and use the outputs in DocRouter `.env`.