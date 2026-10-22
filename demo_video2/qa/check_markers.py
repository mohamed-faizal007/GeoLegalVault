"""QA: every beat's start/end sync marker (and every trimmed-wait marker) must be decodable in its recording."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.argv = sys.argv[:1]
import assemble

bad = 0
for tl in sorted(Path("recordings").glob("*/timeline.json")):
    data = json.loads(tl.read_text())
    for role in sorted({b["role"] for b in data["beats"] if b.get("role")}):
        t = assemble.decode_marks(tl.parent / f"{role}.webm")
        beats = [b for b in data["beats"] if b.get("role") == role and "seq0" in b]
        if not beats:
            print(f"{tl.parent.name}/{role}: legacy recording (no sync markers; caption-snap path)")
            continue
        need = [x for b in beats for x in [b["seq0"], b["seq1"], *[y for w in b["waits"] for y in w]]]
        miss = [x for x in need if x not in t]
        print(f"{tl.parent.name}/{role}: {len(need) - len(miss)}/{len(need)} markers decoded" + (f"  MISSING {miss}" if miss else ""))
        bad += bool(miss)
sys.exit(1 if bad else 0)
