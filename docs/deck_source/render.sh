#!/bin/bash
# 발표자료 빌드 -> 검증 -> PDF -> 슬라이드 PNG
set -e
cd /private/tmp/claude-501/-Users-hantaeho-Documents-ETC-kamp-kamp-competition/e7c21cfb-5d2d-4a63-8752-e767964f782d/scratchpad/deck && DECK_SPEC_ONLY=1 NODE_PATH=/private/tmp/claude-501/-Users-hantaeho-Documents-ETC-kamp-kamp-competition/e7c21cfb-5d2d-4a63-8752-e767964f782d/scratchpad/deck/node_modules node build.js | tail -1
/Users/hantaeho/Documents/ETC/kamp/kamp_competition/.venv/bin/python /private/tmp/claude-501/-Users-hantaeho-Documents-ETC-kamp-kamp-competition/e7c21cfb-5d2d-4a63-8752-e767964f782d/scratchpad/deck/render_charts.py
NODE_PATH=/private/tmp/claude-501/-Users-hantaeho-Documents-ETC-kamp-kamp-competition/e7c21cfb-5d2d-4a63-8752-e767964f782d/scratchpad/deck/node_modules node build.js | tail -1
DECK_FONT="NanumGothic" DECK_OUT=/private/tmp/claude-501/-Users-hantaeho-Documents-ETC-kamp-kamp-competition/e7c21cfb-5d2d-4a63-8752-e767964f782d/scratchpad/deck/out_qa.pptx NODE_PATH=/private/tmp/claude-501/-Users-hantaeho-Documents-ETC-kamp-kamp-competition/e7c21cfb-5d2d-4a63-8752-e767964f782d/scratchpad/deck/node_modules node build.js | tail -1
cd /Users/hantaeho/Documents/ETC/kamp/kamp_competition
.venv/bin/python /private/tmp/claude-501/-Users-hantaeho-Documents-ETC-kamp-kamp-competition/e7c21cfb-5d2d-4a63-8752-e767964f782d/scratchpad/deck/fix_ea.py 발표자료_과제5.pptx "Malgun Gothic"
.venv/bin/python /private/tmp/claude-501/-Users-hantaeho-Documents-ETC-kamp-kamp-competition/e7c21cfb-5d2d-4a63-8752-e767964f782d/scratchpad/deck/fix_ea.py /private/tmp/claude-501/-Users-hantaeho-Documents-ETC-kamp-kamp-competition/e7c21cfb-5d2d-4a63-8752-e767964f782d/scratchpad/deck/out_qa.pptx "NanumGothic"
.venv/bin/python /Users/hantaeho/.claude/skills/synced/b3c08a02-3d0d-4da4-9730-42f08b7f2756_b27599ee-4ece-49ae-aa40-8309977775c7/pptx/scripts/office/validate.py 발표자료_과제5.pptx | tail -1
rm -rf /private/tmp/claude-501/-Users-hantaeho-Documents-ETC-kamp-kamp-competition/e7c21cfb-5d2d-4a63-8752-e767964f782d/scratchpad/deck/out && mkdir -p /private/tmp/claude-501/-Users-hantaeho-Documents-ETC-kamp-kamp-competition/e7c21cfb-5d2d-4a63-8752-e767964f782d/scratchpad/deck/out
/Applications/LibreOffice.app/Contents/MacOS/soffice --headless --convert-to pdf --outdir /private/tmp/claude-501/-Users-hantaeho-Documents-ETC-kamp-kamp-competition/e7c21cfb-5d2d-4a63-8752-e767964f782d/scratchpad/deck/out /private/tmp/claude-501/-Users-hantaeho-Documents-ETC-kamp-kamp-competition/e7c21cfb-5d2d-4a63-8752-e767964f782d/scratchpad/deck/out_qa.pptx >/dev/null 2>&1
.venv/bin/python - <<PY
import pymupdf
d=pymupdf.open("/private/tmp/claude-501/-Users-hantaeho-Documents-ETC-kamp-kamp-competition/e7c21cfb-5d2d-4a63-8752-e767964f782d/scratchpad/deck/out/out_qa.pdf"); print("slides",d.page_count)
for i,p in enumerate(d): p.get_pixmap(dpi=100).save(f"/private/tmp/claude-501/-Users-hantaeho-Documents-ETC-kamp-kamp-competition/e7c21cfb-5d2d-4a63-8752-e767964f782d/scratchpad/deck/out/s{i+1:02d}.png")
PY
