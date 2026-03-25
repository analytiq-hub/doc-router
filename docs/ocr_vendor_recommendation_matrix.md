# OCR Vendor Recommendation Matrix

_Date: March 25, 2026_

## Executive Summary

For DocRouter-style document processing, the best vendor choice depends on the workflow:

- **Submission intake / general OCR / RAG ingestion:** **Mistral OCR 3** is the price leader and is especially attractive when the output is consumed as markdown or structured text.
- **Layout-heavy diligence docs and data rooms:** **Azure Document Intelligence Layout** or **GCP Document AI Layout Parser** offer better value than AWS when you need structure, tables, headings, and reading order.
- **Generic forms / key-value extraction:** **GCP Form Parser** appears materially cheaper than AWS Textract Forms + Tables.
- **Signature detection:** **AWS Textract** has the clearest built-in pricing and feature packaging for signatures.
- **Main cost trap:** **AWS FORMS**. This is the largest source of cost escalation in the current DocRouter-style configuration.

## Pricing Snapshot

These are the closest public price points found for the main vendors. Prices are shown in USD per 1,000 pages.

| Vendor / Mode | Closest Equivalent | Price |
|---|---|---:|
| AWS Textract | OCR only (`DetectDocumentText`) | 1.50 |
| AWS Textract | Tables only | 15.00 |
| AWS Textract | Forms + Tables | 65.00 |
| AWS Textract | Signatures only | 3.50 |
| Azure Document Intelligence | Read OCR | 1.50 |
| Azure Document Intelligence | Layout / Prebuilt Document | ~10.00 |
| GCP Document AI | Enterprise OCR | 1.50 |
| GCP Document AI | Layout Parser | 10.00 |
| GCP Document AI | Form Parser | 30.00 |
| Mistral OCR 3 | OCR + markdown / structured reconstruction | 2.00 |
| Mistral OCR 3 Batch | OCR + markdown / structured reconstruction | 1.00 |
| Mistral OCR 2 | OCR | 1.00 |

## What This Means for DocRouter

Your current AWS Textract feature set is:

- `LAYOUT`
- `TABLES`
- `FORMS`
- `SIGNATURES`

The large cost increase is primarily driven by **FORMS**.

### AWS cost ladder

| AWS configuration | Approx. cost / 1,000 pages |
|---|---:|
| OCR only | 1.50 |
| Signatures only | 3.50 |
| Tables only | 15.00 |
| Forms + Tables | 65.00 |

### Main takeaway

- `LAYOUT` is not the main issue.
- `TABLES` adds a moderate increase.
- `FORMS` is the expensive flag.
- `SIGNATURES` is comparatively cheap when used on its own.

## Recommendation Matrix by Workflow

| Workflow | Primary Need | Recommended Vendor | Why | Avoid / Caveat |
|---|---|---|---|---|
| Submission intake | OCR, markdown, chunking for RAG | **Mistral OCR 3** | Lowest cost among strong OCR options and well-suited for markdown-oriented downstream processing | Not a full drop-in replacement for native field schemas |
| Broker emails + attachments | Cheap OCR with decent structure | **Mistral OCR 3** or **Azure Read/Layout** | Good economics; layout support matters for mixed attachment types | Azure pricing should be checked in-region |
| Data room ingestion | Headings, sections, tables, reading order | **Azure Layout** or **GCP Layout Parser** | Better value than AWS for layout-heavy docs | May need extra logic for field extraction |
| Underwriting guidelines / policy wording | Clean structure, hierarchy, tables | **Azure Layout** | Strong document structure extraction | Public Azure pricing pages can be inconsistent |
| Financial statements | Tables and document structure | **GCP Layout Parser** or **Azure Layout** | More attractive than AWS Tables/Forms for structured extraction | Tables still need post-processing logic |
| Standard ACORD / supplemental applications | Key-value extraction | **GCP Form Parser** | Much cheaper than AWS Forms + Tables in public pricing | Need to validate quality on your real forms |
| Signature-heavy workflows | Signature detection | **AWS Textract** | Clearest built-in signature feature packaging | Costs rise fast if Forms is enabled unnecessarily |
| Complex heterogeneous insurance forms | Generic form extraction across many templates | **GCP Form Parser** first, AWS second | GCP appears cheaper; AWS may still be attractive if already deeply integrated | Benchmark extraction quality before switching |
| Reinsurance diligence with mixed documents | Hybrid workflow | **Mix vendors by doc type** | Cheap OCR for most docs, premium extraction only where needed | Requires routing logic in pipeline |

## Best Practical Strategy

A strong production strategy for DocRouter would be:

### Tier 1: Cheap default OCR
Use **Mistral OCR 3** or **Azure Read/Layout** for:
- broker submission packets
- emails
- policy wording
- engineering reports
- board decks
- memos
- data room documents meant mainly for search, summarization, or review

### Tier 2: Escalate only when needed
Use **GCP Form Parser** or **AWS Textract Forms** only for:
- ACORD forms
- supplemental applications
- structured underwriting questionnaires
- documents where key-value extraction materially saves human review time

### Tier 3: Specialized signature pass
Use **AWS Textract Signatures** only on document classes where signature detection matters.

This avoids paying AWS Forms pricing on every page.

## Suggested Routing Logic

| Document Type | Recommended OCR / Extraction Path |
|---|---|
| Email PDF, memo, report, deck | Mistral OCR 3 |
| Policy wording, contracts, guidelines | Azure Layout or Mistral OCR 3 |
| Financial statements | Azure Layout or GCP Layout Parser |
| ACORD forms | GCP Form Parser |
| Supplemental underwriting form | GCP Form Parser or AWS Textract Forms |
| Signature page | AWS Textract Signatures |
| Mixed packet with many document types | First classify, then route to the cheapest adequate engine |

## Integration Considerations

### AWS Textract
**Pros**
- Mature AWS integration
- Straightforward if already on AWS
- Clear built-in signatures support

**Cons**
- Expensive once Forms is enabled
- Cost rises sharply for broad default use

### Azure Document Intelligence
**Pros**
- Strong layout/document analysis
- Good fit for structure-heavy documents
- Often cheaper than AWS for layout extraction

**Cons**
- Public pricing visibility can be inconsistent
- Signature support is less cleanly packaged than AWS

### GCP Document AI
**Pros**
- Strong form parser economics
- Good balance of layout + field extraction offerings

**Cons**
- Another cloud dependency if you are primarily AWS/Azure
- Requires benchmarking on insurance-specific forms

### Mistral OCR
**Pros**
- Extremely attractive pricing
- Good for markdown-oriented processing and RAG ingestion
- Likely best default OCR economics

**Cons**
- Not a full managed document AI suite in the same sense as AWS/Azure/GCP
- You may need more custom downstream extraction logic

## Final Recommendation

For a DocRouter-style insurance document platform:

1. **Default OCR path:** **Mistral OCR 3**
2. **Layout-heavy structured docs:** **Azure Layout** or **GCP Layout Parser**
3. **Key-value / forms extraction:** **GCP Form Parser**
4. **Signature-specific detection:** **AWS Textract Signatures**
5. **Do not enable AWS FORMS by default across all pages**

The main optimization is simple:

> Use the cheapest OCR engine that is good enough for the document class, and only escalate to premium field extraction on the subset of documents that truly need it.

## Notes

Azure public pricing was less clearly rendered than the other vendors when this report was compiled, so Azure numeric estimates should be rechecked for the exact target region before procurement or production budgeting.
