# DocRouter demo: presenter script

Generated from `steps.yaml`. Edit the captions there, not here.

## DocRouter

0. DocRouter: an AI index for the insurance document store.
   _Screen: title card: An AI index for the document store_

## 1 · The document store

1. This is a carrier's document store: claim files and policy packets, auto and home, as they come in. DocRouter indexes it and sits beside your system of record. It doesn't replace it.
   _Screen: open /orgs/{ins}/docs_
2. Cases group what belongs together. This is one homeowner claim: eight documents from five sources, in one place.
   _Screen: click a[href$="/cases/{home_case}"]_

## 2 · The agent builds a pipeline

3. Here's the first notice of loss for that claim. Normally an adjuster rekeys this.
   _Screen: click 01_first_notice_of_loss.pdf_
4. No data-science team. The person who knows the document describes it, and the agent builds the pipeline: a tag, a schema, and a versioned prompt.
   _Screen: click Chat → type "Create a tag, schema and prompt to process first notice of loss documents for any line of business, then run it on this document. Keep the document's existing tags. The LLM should be the newest Gemini Flash." → agent works (~80s live)_
5. Structured fields, from a document nobody had configured five minutes ago.
   _Screen: click Extraction_
6. The prompt is versioned and tied to a tag and a schema. A change to it is a release, not an edit in a chat log.
   _Screen: open /orgs/{ins}/prompts_

## 3 · Tags trigger the work

7. From now on it's a rule. A new loss notice arrives, from the UI, the API or a connector, tagged First Notice of Loss…
   _Screen: open /orgs/{ins}/docs?tab=upload → upload FNOL copy → click Continue → click claim → click auto → click Continue → click Upload files_
8. …and the pipeline runs on its own: OCR, then the same extraction. A different line of business, the same schema.
   _Screen: extraction runs (~30s live)_

## 4 · Cited answers

9. This is the agent part. It answers from the policy the carrier actually issued, and it quotes the passage it read.
   _Screen: open /orgs/{ins}/knowledge-bases?tab=edit&kbId={kb} → click Chat → type "What deductible applies to a roof claim at 12 Maple Lane, and which policy form governs it? Quote the passages you used."_
10. A model that remembers a form won't survive an audit. One that quotes the form will.

## 5 · A mixed packet, end to end

11. Real packets arrive mixed. This flow starts whenever a document is uploaded with the tag Surgery Pre-Op Schedule.
   _Screen: open /orgs/{test}/flows/{flow} → open node "Document event trigger"_
12. To show it now, we've pinned a sample packet on the trigger: 13 pages, three patients, one PDF.
13. Watch it run.
   _Screen: click button_
14. It splits the packet into pages, so each page is handled on its own.
   _Screen: open node "Document Split" → Table view_
15. It reads the text of every page.
   _Screen: open node "Run OCR" → Table view_
16. The model labels each page and pulls out who it belongs to: name, date of birth, MRN. Three pages have no name on them: an advance-directives note and a nurse signature.
   _Screen: open node "Run LLM" → Table view_
17. Then plain code, not a model, assigns every page to a patient: by MRN, by name, and by where the page sits in the packet. Those three pages go to the right patient.
   _Screen: open node "Code (Python)" → Schema view_
18. One clean file per patient, each traced back to its source pages.
   _Screen: Binary view_
19. And this is the oversight hook. human_review is 0: every page was placed, so the packet goes straight through. If a page couldn't be placed, it would be 1, and the next step would hold the packet for a person.
   _Screen: Schema view_

## 6 · Everything is an API

20. Every screen you just saw runs on the same REST API: documents, tags, schemas, prompts, knowledge bases, flows. Anything you can do in the UI, your claims system or your data lake can do through the API.
   _Screen: Swagger /docs_
21. And your own agents can drive it too, through the Python and TypeScript SDKs or the MCP server.

## DocRouter

22. A document store isn't an AI system until it's indexed. DocRouter does the indexing. The agent recommends. People decide.
   _Screen: title card: The agent recommends. People decide._

## Live demo

23. Want to see it on your own documents? Scan the code to book a live demo, or talk to us here at the booth.
   _Screen: title card: See it on your own documents_
