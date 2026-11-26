# Datos Insights 2026 booth demo

An automated walkthrough of DocRouter (about 5 minutes live, shorter once the waits are sped up)
that drives the real UI against a local stack and shows the voice-over as captions.

| File | What it does |
|---|---|
| `steps.yaml` | The demo: config, then one entry per beat with its caption and UI actions |
| `run-demo.ts` | Puppeteer runner: live window, headless recording, or booth loop |
| `reset.py` | Puts the `insurance` and `test` orgs back to the starting state |
| `postprocess.ts` | Turns a recording into an MP4 with the long waits sped up |
| `render-script.ts` | Prints the presenter script from `steps.yaml` |
| `overlay.ts` | Caption bar, part label, cursor and highlight boxes injected into each page |
| `title-card.ts` | Title cards in the video-poster design (pattern background from the site's `_brand/demo-poster`) |
| `render-cards.ts` | Renders replacement title cards and caption bars for patching a recorded video |
| `patch-video.sh` | Lays those over an existing MP4, at timings measured for one take |
| `probe*.ts` | Dev helpers used to find selectors; not part of a run |

## The story

1. **The document store** (`insurance` org): document list, then case `CLAIM-HOME-0001`.
2. **The agent builds a pipeline**: on the home FNOL, the chat agent creates a tag, schema and
   prompt and runs the extraction (live LLM, about 80 s).
3. **Tags trigger the work**: a copy of the auto FNOL is uploaded with the new tag; OCR and the
   extraction run automatically (about 30 s). Retagging an existing document does *not* run
   prompts; only an upload does.
4. **Cited answers**: knowledge base `Policy Library` answers a deductible question and quotes
   the policy.
5. **A mixed packet** (`test` org, flow *Surgery schedule*): runs on the pinned 13-page packet
   and walks node by node to `human_review`.
6. **Everything is an API**, closing line, and a call to action to book a live demo.

## Prerequisites

- `make dev` running (FastAPI on :8000 with its in-process workers, Vite on :5173).
- `tests-ui` dependencies installed: `cd tests-ui && npm install`.
- `ffmpeg` on `PATH` for recording.
- `.env` in this folder (git-ignored) with `DEMO_EMAIL`, `DEMO_PASSWORD`, `DEMO_NAME`.
- **SPU credits.** One full pass uses about 30 credits in `insurance` and a few in `test`.
  `reset.py` prints what is left. Credits can only be added by a sysadmin, from the org's
  subscription page or `POST /v0/orgs/{org_id}/payments/credits/add`.

## Commands

From the repo root, with the venv active:

```bash
python tests-ui/demo/datos-2026/reset.py --setup    # once: demo user, knowledge base
python tests-ui/demo/datos-2026/reset.py            # before every run
```

From this folder:

```bash
node run-demo.ts                       # live, full-screen Chrome window
node run-demo.ts --loop                # booth mode: reset + run, forever
node run-demo.ts --record              # headless; writes out/demo-<stamp>.webm + timeline
node postprocess.ts out/demo-<stamp>.webm     # -> out/demo-<stamp>.mp4, waits sped up 6x
node run-demo.ts --headless --shots --only 11-24   # debug a range; screenshot per step
node render-script.ts > script.md      # presenter script
```

`--only` and `--from` don't replay earlier steps, so start a range at a step that opens its own
page (0, 1, 11 or 20).

## What reset.py changes

In `insurance`: deletes the uploaded FNOL copy, every prompt and schema, and any tag outside
`baseline_tags`; restores the tags on the two FNOLs and the home policy; deletes the demo
user's agent threads on the home FNOL. In `test` it only checks that the surgery flow is active
and has a pinned input.

## Changing wording or cards without re-recording

Title cards and captions can be replaced in a finished MP4, which keeps a good take and costs no
SPU credits:

```bash
# after editing steps.yaml
node render-cards.ts --cards 0,22,23 --captions 1,2 --fade-captions 1     # -> out/patch/*.png
./patch-video.sh out/web/docrouter-datos-2026.mp4 out/web/docrouter-datos-2026-v2.mp4
```

The timings at the top of `patch-video.sh` belong to the 2026-11-25 take; a new take needs
them re-measured (frame differences in the caption area, at 30 fps). Caption patches are drawn
in the bar's measured solid colour; where a bar fades in after a page load, the script restores
a clean background strip and fades in the real 92%-opaque bar, so old and new text never mix.
The caption bar is `box-sizing: border-box` (1400 px wide, as on the app pages).

## Published files

`media.docrouter.ai/demos/datos-2026/` (S3 bucket `analytiq-media-890742589311`, see
`analytiq-terraform/applications/media`): `docrouter-datos-2026-v2.mp4` and `poster-v3.jpg` are
current. Never overwrite a published file; upload the next version under a new name.

## Before the show

- The call-to-action card shows the banner QR code, which encodes `https://docrouter.ai/demo`.
- Record a few takes and keep the cleanest; the agent's wording varies between runs.
