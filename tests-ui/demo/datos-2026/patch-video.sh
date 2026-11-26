#!/usr/bin/env bash
# Lay re-rendered title cards and caption bars over an already-recorded demo video, so
# wording and design changes don't need a new recording.
#
#   node render-cards.ts --cards 0,22,23 --captions 1,2 --fade-captions 1   # out/patch/*.png
#   ./patch-video.sh out/web/docrouter-datos-2026.mp4 out/web/docrouter-datos-2026-v2.mp4
#
# The timings below are for the 2026-11-25 take (demo-2026-11-25T22-34-44), measured frame by
# frame in the final MP4. A new take needs new timings. Times sit half a frame (1/60 s) before
# each frame boundary at 30 fps, so every overlay starts and ends on the right frame.
set -euo pipefail

IN=${1:?input mp4}
OUT=${2:?output mp4}
P=$(dirname "$0")/out/patch

OPENING_END=2.85            # opening title card: 0 -> 2.867
CAP1_FADE_START=4.02        # step 1 caption bar fades in 4.033 -> 4.267 after the page loads.
CAP1_FADE=0.21              #   During the fade: clean background strip + real-styled bar fading in.
CAP1_SOLID=4.28             #   After it: the solid bar covers the old one.
CLEAN_AT=4.000              #   Frame with the page loaded and no bar yet (source of the clean strip).
STRIP_X=220; STRIP_Y=895; STRIP_W=1480; STRIP_H=185   # bar box 260,907 1400x145 plus shadow
CAP2_START=13.22            # step 2 caption replaces step 1 at 13.233
CAP2_END=19.52              # step 3 caption takes over at 19.533
TAGLINE_START=206.32        # old tagline caption appears over the API page at 206.333; card at 206.433
CTA_START=212.52            # call-to-action card: 212.533 -> end

for f in card-00 card-22 card-23 caption-01 caption-02 caption-01-fade; do
  [[ -f "$P/$f.png" ]] || { echo "missing $P/$f.png; run render-cards.ts first" >&2; exit 1; }
done

DURATION=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$IN")
ffmpeg -v error -y -ss "$CLEAN_AT" -i "$IN" -frames:v 1 \
  -vf "crop=${STRIP_W}:${STRIP_H}:${STRIP_X}:${STRIP_Y}" "$P/clean-strip.png"

ffmpeg -v error -stats -y -i "$IN" \
  -loop 1 -i "$P/card-00.png" -loop 1 -i "$P/card-22.png" -loop 1 -i "$P/card-23.png" \
  -loop 1 -i "$P/caption-01.png" -loop 1 -i "$P/caption-02.png" \
  -loop 1 -i "$P/clean-strip.png" -loop 1 -i "$P/caption-01-fade.png" \
  -filter_complex "
    [7:v]format=rgba,fade=in:st=${CAP1_FADE_START}:d=${CAP1_FADE}:alpha=1[fade1];
    [0:v][1:v]overlay=enable='lt(t,${OPENING_END})'[v0];
    [v0][6:v]overlay=x=${STRIP_X}:y=${STRIP_Y}:enable='gte(t,${CAP1_FADE_START})*lt(t,${CAP1_SOLID})'[f1];
    [f1][fade1]overlay=enable='gte(t,${CAP1_FADE_START})*lt(t,${CAP1_SOLID})'[f2];
    [f2][4:v]overlay=enable='gte(t,${CAP1_SOLID})*lt(t,${CAP2_START})'[v2];
    [v2][5:v]overlay=enable='gte(t,${CAP2_START})*lt(t,${CAP2_END})'[v3];
    [v3][2:v]overlay=enable='gte(t,${TAGLINE_START})*lt(t,${CTA_START})'[v4];
    [v4][3:v]overlay=enable='gte(t,${CTA_START})'[out]" \
  -map "[out]" -t "$DURATION" -r 30 \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -movflags +faststart "$OUT"

echo "$OUT"
