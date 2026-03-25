# DocRouter Product Strategy Memo and Feature-Priority Roadmap

## Purpose

This memo outlines how **DocRouter** can be positioned and expanded to serve a Microsoft-centric commercial insurance or reinsurance buyer that manages submissions, diligence materials, policy wording, market research, and underwriting memos in **Microsoft SharePoint**.

It also explains how **knowledge bases** should fit into the product strategy, and recommends a phased feature roadmap to make DocRouter more competitive with platforms such as **Hyperscience**, **Instabase**, **Indico**, and underwriting workbench vendors.

---

## Executive Summary

### Recommended market position

DocRouter should be positioned as:

> **The submission-intelligence and evidence layer for Microsoft-first underwriting teams.**

In this model:
- **SharePoint** remains the system of record for files and permissions.
- **Microsoft 365 / Teams / Power Platform / Copilot** remain the collaboration and workflow surface.
- **DocRouter** becomes the system that reads, organizes, validates, compares, explains, and summarizes the submission.

This is a stronger commercial position than selling DocRouter as a generic OCR or extraction tool.

### Strategic thesis

DocRouter should evolve from:
- **document processor with prompts, schemas, and knowledge bases**

into:
- **submission workspace with KB-backed reasoning, reviewer operations, and Microsoft-native integration**

That direction aligns better with how underwriters actually work:
- packet intake
- document splitting and classification
- clause and red-flag review
- cross-document reconciliation
- follow-up tracking
- memo drafting
- market and guideline lookup
- evidence-backed decisions

---

## Why Microsoft-first integration is the right wedge

Many insurers and reinsurers already store submissions, diligence reports, policy drafts, and committee materials in **SharePoint**. They want AI capabilities without moving their content and without breaking their existing governance model.

DocRouter has a strong opportunity here because it already has:
- open-source deployment and self-hosting options
- REST APIs
- webhooks
- workflow integrations
- knowledge bases
- model flexibility
- document-centric AI processing

### Best-fit architecture

The best architecture is:

1. A document or packet lands in **SharePoint**.
2. A **Microsoft Graph change notification** or SharePoint-triggered workflow detects the change.
3. An **Azure Function**, **Logic App**, or similar integration service retrieves the file and metadata.
4. The service sends the file to **DocRouter** with routing metadata.
5. DocRouter processes the content, extracts structured data, runs prompts and validations, and optionally uses one or more knowledge bases.
6. Results are written back into **SharePoint columns**, **Dataverse**, or a downstream underwriting queue.
7. Underwriters interact through **SharePoint**, **Teams**, **Power Apps**, or **Copilot Studio**.

### Why this works commercially

This lets DocRouter sell into enterprises without asking them to replace:
- SharePoint
- Entra ID / Microsoft security
- Teams
- Power Platform
- existing underwriting systems

Instead, DocRouter adds the missing intelligence layer.

---

## Role of knowledge bases in the product strategy

## Short answer

**Yes — knowledge bases should play a major role.**

But the right design is **not** a single monolithic knowledge base.

The strongest model is a **three-layer knowledge architecture**:

### 1. Global rules knowledge base
Reusable underwriting knowledge shared across many submissions.

Examples:
- underwriting guidelines
- exclusions and appetite rules
- red-flag language
- policy clause playbooks
- pricing guidance
- referral criteria
- memo templates
- surveillance and renewal procedures

### 2. Submission workspace knowledge base
Knowledge specific to a single live submission or deal.

Examples:
- broker submission packet
- diligence and market reports
- emails and notes
- policy drafts and markups
- follow-up questions and responses
- internal review notes
- meeting notes
- final memo and attachments

### 3. Market and reference knowledge base
External and semi-reusable reference content used across multiple deals.

Examples:
- comparable transactions
- third-party market reports
- sector reference material
- legal or regulatory notes
- recurring broker / cedent reference materials

## Should there be a knowledge base for each submission?

**Yes, often — but productized as a “submission workspace,” not just a raw KB object.**

A per-submission KB is useful because it gives the system:
- scoped search
- case-specific chat
- localized reasoning context
- case memory across multiple review sessions
- better memo drafting and citation

However, the product should avoid making users think in terms of low-level KB administration.

The better abstraction is:

> **Submission Workspace = case record + linked documents + retrieval configuration + review state + knowledge access**

Internally, that workspace may map to one or more DocRouter knowledge bases, but the user experience should be case-first.

### Why this matters

Vendors like Hyperscience and Instabase are strong not only because they extract fields, but because they organize work around a **submission**, **case**, or **workflow queue**. DocRouter should do the same.

---

## Competitive positioning

## Where DocRouter is already strong

Compared with larger commercial platforms, DocRouter has meaningful advantages in:
- openness and self-hosting
- source-code access and control
- deployment flexibility
- API-first integration
- customizable workflows
- model flexibility
- lower lock-in risk
- ability to fit inside an enterprise Azure / SharePoint stack

## Where DocRouter is currently weaker

Compared with Hyperscience, Instabase, or Indico, DocRouter appears weaker in:
- first-class submission / case / packet management
- native SharePoint connector packaging
- reviewer workbench UX
- queueing and operations tooling
- validation and exception-routing depth
- packaged insurance workflow templates
- out-of-the-box enterprise workflow polish

## How to position against each vendor

### vs. Microsoft native tools
Position DocRouter as:
- deeper document understanding
- better cross-document reasoning
- more flexible extraction and workflow orchestration
- stronger support for self-hosting and custom AI logic

### vs. Hyperscience
Position DocRouter as:
- more open
- more customizable
- easier to fit into bespoke enterprise stacks

But acknowledge that Hyperscience is currently more mature in:
- submission handling
- operational queues
- supervision and review
- packaged validation workflows

### vs. Instabase
Position DocRouter as:
- simpler and more open
- easier to self-host and extend
- better fit for buyers that want control over their document intelligence stack

But acknowledge that Instabase is currently stronger in:
- packet splitting
- document classification
- case-centric review flows
- highly packaged insurance submission workflows
- native enterprise connector polish

### vs. Indico
Position DocRouter as:
- more developer-friendly
- more open and infrastructure-controllable

But acknowledge that Indico is more insurance-packaged around intake, orchestration, and next-best-action style workflows.

### vs. underwriting workbench vendors
Send and Cytora are closer to full underwriting operating platforms than pure document-AI platforms.

DocRouter should not claim to replace them outright.

A stronger position is:

> **DocRouter powers the document-intelligence, evidence, and review layer underneath a Microsoft-first underwriting operating model.**

---

## Product strategy

## Strategic objective

Build the leading **Microsoft-native submission intelligence layer** for commercial underwriting and reinsurance teams.

## Product principles

1. **Microsoft is the outer shell.**
   SharePoint, Teams, Entra ID, Power Platform, and Copilot are part of the solution, not the enemy.

2. **Submission is the core object.**
   The system should organize work around a packet / case / submission, not just around a document.

3. **Knowledge is layered.**
   Global rules, market references, and submission-specific knowledge should be separable and composable.

4. **Every output should be evidence-backed.**
   Extracted fields, red flags, clause findings, and memo sections should point back to source evidence.

5. **Human review is a first-class workflow.**
   Review, override, assign, escalate, and measure throughput.

6. **Configuration beats services-heavy customization.**
   Insurance and reinsurance templates should be packaged into the product.

## Core use cases to support

1. SharePoint submission intake
2. Packet splitting and classification
3. Cross-document extraction and reconciliation
4. Clause and red-flag review
5. Missing-document and missing-data detection
6. Follow-up issue tracking
7. Underwriting memo drafting with citations
8. Market-comparable evidence packs
9. Surveillance and renewal review support

---

## Feature-priority roadmap

## Phase 1 — Microsoft-native intake and distribution

### Goal
Make DocRouter easy to adopt inside a Microsoft-heavy enterprise.

### Features
1. **Native SharePoint / Microsoft Graph connector**
   - monitor selected sites and libraries
   - incremental sync and change detection
   - preserve SharePoint metadata and URLs
   - handle version updates

2. **Routing rules from SharePoint metadata**
   - library / folder / content type / site rules
   - map to DocRouter tags, prompts, schemas, and workflows

3. **Write-back into SharePoint and Dataverse**
   - extracted fields
   - case status
   - review-needed flags
   - links to source evidence and review UI

4. **Power Platform custom connector**
   - use DocRouter OpenAPI to enable Power Automate / Power Apps integration

5. **Teams notifications and actions**
   - review required
   - processing complete
   - follow-up needed

### Why Phase 1 matters
This is the fastest way to reduce integration friction and make DocRouter “feel native” inside Microsoft environments.

---

## Phase 2 — Submission workspace as a first-class object

### Goal
Close the biggest workflow gap versus Instabase and Hyperscience.

### Features
1. **Case / Submission / Workspace object**
   - case ID
   - insured / cedent / broker / counterparty metadata
   - stage and owner
   - linked documents and versions

2. **Submission packet ingestion**
   - treat a multi-file upload or folder as a single submission
   - support email-style packet ingestion over time

3. **Packet splitting and classification**
   - separate broker presentations, schedules, loss runs, policy drafts, diligence reports, etc.

4. **Submission-scoped search and chat**
   - ask questions only over the current submission
   - cite to source pages and documents

5. **Cross-document field reconciliation**
   - compare values across multiple documents
   - surface conflicts and unresolved discrepancies

6. **Version-aware comparison**
   - compare successive policy drafts, markups, and diligence versions

### Why Phase 2 matters
This transforms DocRouter from a document processor into a case-oriented underwriting workspace.

---

## Phase 3 — Reviewer operations and exception handling

### Goal
Add Hyperscience-style reviewer workflow depth.

### Features
1. **Reviewer workbench**
   - side-by-side source view and extracted fields
   - field-level provenance
   - confidence indicators
   - quick approve / reject / override actions

2. **Confidence thresholds and routing**
   - auto-accept
   - send-to-review
   - hard fail / soft fail

3. **Assignment queues and SLA controls**
   - owner assignment
   - aging
   - priority and deadline controls

4. **Audit trail and override logging**
   - who changed what
   - when
   - why

5. **Follow-up tracker**
   - open questions
   - missing documents
   - unresolved red flags

6. **Operations metrics**
   - queue aging
   - extraction confidence trends
   - reviewer throughput
   - straight-through processing rate

### Why Phase 3 matters
This is what makes the product feel operationally complete, not just technically capable.

---

## Phase 4 — Retrieval and knowledge quality

### Goal
Make knowledge bases central, reliable, and scalable for underwriting workflows.

### Features
1. **Hybrid lexical + semantic search**
   - improve exact-match behavior for names, clause titles, identifiers, and short queries

2. **Workspace-scoped retrieval filters**
   - submission-only search
   - document-type filters
   - version filters

3. **Source-aware answer generation**
   - evidence panels
   - citation snippets
   - conflicting-source display

4. **Retrieval evaluation framework**
   - benchmark query sets
   - answer-quality evaluation
   - regression monitoring

5. **Tiered knowledge composition**
   - combine global rules KB + submission workspace + market KB dynamically

6. **Case memory features**
   - prior reviewer notes
   - prior questions and answers
   - resolved issues

### Why Phase 4 matters
If knowledge bases are central to the strategy, retrieval quality becomes a product-defining capability.

---

## Phase 5 — Insurance and reinsurance starter packs

### Goal
Reduce services-heavy onboarding and increase product relevance.

### Starter packs to ship
1. **Submission intake starter pack**
2. **Clause red-flag review starter pack**
3. **Underwriting memo starter pack**
4. **Market-comps / evidence pack starter pack**
5. **Surveillance / renewal review starter pack**
6. **Surety / specialty underwriting rules starter pack**

### Included elements
- schemas
- prompts
- routing rules
- review workflows
- sample dashboards
- example knowledge base structures

### Why Phase 5 matters
This lets DocRouter look more like a vertical solution without giving up its flexible platform roots.

---

## Recommended packaging

### Product packaging concept

#### Tier 1: Microsoft Submission Intelligence
Best for Microsoft-first underwriting teams.

Includes:
- SharePoint connector
- submission workspace
- review workbench
- Teams / Power Platform integration
- memo drafting and evidence view

#### Tier 2: Self-Hosted Enterprise Intelligence
Best for privacy-sensitive or regulated environments.

Includes:
- Kubernetes deployment
- private model configuration
- custom workflows
- enterprise authentication
- custom knowledge architecture

#### Tier 3: Vertical Insurance Starter Bundle
Best for faster go-live in underwriting operations.

Includes:
- insurance starter packs
- packet workflows
- red-flag review templates
- underwriting memo templates

---

## Success metrics

Recommended product and GTM metrics:

### Adoption metrics
- time to first SharePoint-connected workflow
- number of active submission workspaces
- number of users reviewing cases in Teams / SharePoint / Power Apps

### Automation metrics
- straight-through processing rate
- average documents processed per submission
- average time from upload to review-ready output

### Quality metrics
- field-level precision / recall
- clause red-flag detection quality
- memo citation accuracy
- retrieval success rate for submission chat

### Business metrics
- underwriting cycle-time reduction
- reviewer capacity gain
- decrease in manual packet triage
- increase in throughput per underwriter or analyst

---

## Recommended near-term priorities

If only a few items can be funded immediately, prioritize in this order:

1. **Native SharePoint / Microsoft Graph connector**
2. **Submission workspace object**
3. **Reviewer workbench**
4. **Hybrid retrieval and submission-scoped knowledge**
5. **Insurance / reinsurance starter packs**
6. **Power Platform and Copilot packaging**

This sequence gives DocRouter the strongest path to becoming a credible Microsoft-first underwriting solution.

---

## Reference URLs

### DocRouter
- DocRouter GitHub: https://github.com/analytiq-hub/doc-router
- DocRouter open source overview: https://docrouter.ai/docs/open-source/
- DocRouter how it works: https://docrouter.ai/docs/how-it-works/
- DocRouter knowledge bases: https://docrouter.ai/docs/knowledge-bases/
- DocRouter webhooks: https://docrouter.ai/docs/webhooks/

### Microsoft
- Microsoft Graph change notifications: https://learn.microsoft.com/en-us/graph/change-notifications-overview
- Microsoft Copilot Studio knowledge sources: https://learn.microsoft.com/en-us/microsoft-copilot-studio/knowledge-copilot-studio
- Microsoft custom connectors overview: https://learn.microsoft.com/en-us/connectors/custom-connectors/
- Microsoft 365 Copilot connectors API / Microsoft Graph external content: https://learn.microsoft.com/en-us/graph/connecting-external-content-connectors-api-overview

### Competitive reference points
- Send underwriting platform: https://send.technology/products/direct-underwriting
- Indico submissions ingestion: https://indicodata.ai/platform/submissions-ingestion/
- Instabase broker submissions processing: https://instabase.com/product-solutions/broker-submissions-processing/
- Instabase insurance overview: https://www.instabase.com/solutions/insurance
- Hyperscience submissions concept: https://help.hyperscience.com/v41/docs/what-is-a-submission

---

## Closing recommendation

The best strategy is to evolve DocRouter from a flexible document-processing platform into a **Microsoft-native submission workspace platform**.

The key moves are:
- make SharePoint integration first-class
- elevate submission workspaces above raw document objects
- use knowledge bases as layered case memory
- add reviewer operations and exception handling
- package insurance and reinsurance starter flows

That path preserves DocRouter’s strongest differentiators — **openness, self-hosting, flexibility, and extensibility** — while closing the most important workflow gaps versus more packaged enterprise competitors.
