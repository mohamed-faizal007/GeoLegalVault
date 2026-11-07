"""Build SPEAKER_SCRIPT.md and SPEAKER_SCRIPT.txt for reading aloud over GeoLegalVault_Demo_v2_silent_captions.mp4.

    python demo_video2/make_speaker_script.py

Reads captions.srt + timeline.json (exact sentence starts on the silent video) and narration.py (the AI wording,
beat order) and speaker_content.py (the trimmed wording). Checks that every sentence fits 130 words per minute in the
time the video gives it, then writes the two files. Read-only for everything else; nothing is recorded or sent.
"""
import json
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import narration  # noqa: E402
from speaker_content import C  # noqa: E402

MAX_WPM = 130
OVERHEAD = 0.6          # lead-in + breathing gap inside every sentence slot (0.25 s lead, 0.45 s gap in the video)
CUT = 19 * 60 + 28.0    # the final video keeps the main video only up to 19:28
SHIFT = 24              # main-video timestamps are about 24 s later in the final video (23.98 s with a 24.48 s title clip)
SCENE0 = ("Good day. This is GeoLegalVault, a course project for Blockchain Technologies, C-S-E four-oh-seven-eight, "
          "at Vellore Institute of Technology. We are Ekanath D V, S. Mohamed Faizal and Rohan Julius Preetan, "
          "with our faculty, Doctor Jayanthi R. This is a live demonstration.")
PAUSE_MIN = 3.0         # show a [PAUSE] when the video holds at least this long after the sentence at MAX_WPM
LIMITS = {("s01", "b5"): "tamper-evident, not prevented",
          ("s05", "k6"): "geofencing is policy, not a guarantee of location",
          ("s16", "k10"): "the audit log has no hash chain yet"}

# spoken form -> pronunciation hint, shown in [brackets] after its first appearance
HINTS = [
    (r"GeoLegalVault", "JEE-oh LEE-gul vawlt"),
    (r"geofence", "JEE-oh-fence"),
    (r"SHA-256", "say: S-H-A two-fifty-six"),
    (r"Ethereum", "eh-THEER-ee-um"),
    (r"Sepolia", "seh-POH-lee-uh"),
    (r"maker checker violation", "on screen: MAKER_CHECKER_VIOLATION"),
    (r"geofence denied", "on screen: GEOFENCE_DENIED"),
    (r"location low confidence", "on screen: LOCATION_LOW_CONFIDENCE"),
    (r"access denied", "on screen: ACCESS_DENIED"),
    (r"Etherscan", "EE-ther-scan"),
    (r"Ether\b", "EE-ther"),
    (r"four-oh-four", "404"),
    (r"four-oh-three", "403"),
    (r"RustFS", "Rust-F-S"),
    (r"Cloudflare R2", "say: Cloudflare R-two"),
    (r"MongoDB", "MON-go-D-B"),
    (r"Merkle", "MUR-kul"),
    (r"pre-signed", "pre-SIGNED"),
    (r"Superseded", "soo-per-SEE-did"),
    (r"HQ Campus", "H-Q"),
    (r"NOT ANCHORED", "on screen: NOT_ANCHORED"),
    (r"ANCHOR MISSING", "on screen: ANCHOR_MISSING"),
    (r"FILE MISSING", "on screen: FILE_MISSING"),
    (r"CHAIN UNREACHABLE", "on screen: CHAIN_UNREACHABLE"),
    (r"login rate limits", "on screen: login_rate_limits"),
    (r"FastAPI", "Fast-A-P-I"),
    (r"web3\.py", "web-three dot P-Y"),
    (r"Solidity", "sol-ID-ih-tee"),
    (r"CI pipeline", "C-I pipeline"),
    (r"SEC-01", "S-E-C zero-one"),
    (r"SEC-03", "S-E-C zero-three"),
    (r"OPS-01", "O-P-S zero-one"),
    (r"CMP-01", "C-M-P zero-one"),
]

TERMS = [
    ("Geofence", "a virtual boundary drawn on a map; uploads and approvals are allowed only inside it."),
    ("SHA-256 hash", "a 64-character fingerprint of a file; change one byte and the whole fingerprint changes."),
    ("Anchor / anchoring", "writing that fingerprint (never the file) to the public Sepolia test network."),
    ("Sepolia", "a free Ethereum test network. Test Ether has no real value."),
    ("Maker-checker", "the person who made a document may not be the one who approves it."),
    ("Clearance", "Public < Internal < Confidential < Restricted < Top Secret; a document above yours is a 404."),
    ("404 vs 403", "404 = not found, 403 = forbidden. 404 is used so a hidden document is not confirmed to exist."),
    ("Pre-signed link", "a download link that works for 60 seconds; the file never passes through the API."),
    ("Supplementary view", "a read-only look at the database or storage, labelled as such, not part of the app."),
    ("Fail-closed", "if the system is not sure about the location, it says no."),
    ("Service wallet", "the one backend wallet that signs every anchor; users never sign."),
    ("Merkle tree", "a batching scheme for hashes; not used here. One hash per file."),
]


def fmt(sec):
    sec = max(sec, 0)
    return f"{int(sec // 60)}:{int(sec % 60):02d}"


def beat_windows():
    """Exact start of every sentence on the silent video, rebuilt from captions.srt (first caption - 0.25 s lead)."""
    tl = json.loads((ROOT / "timeline.json").read_text())
    blocks = (ROOT / "captions.srt").read_text(encoding="utf-8").strip().split("\n\n")

    def sec(t):
        h, m, s = t.replace(",", ".").split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    caps = []
    for b in blocks:
        ln = b.split("\n")
        a, z = ln[1].split(" --> ")
        caps.append((sec(a), sec(z)))
    out, i = [], 0
    for sc in narration.SCENES:
        for key, text in sc["lines"]:
            chunks = [c.strip() for c in re.split(r"(?<=[.,:;?!])\s+", text) if c.strip()]
            merged, cur = [], ""
            for c in chunks:
                if cur and len(cur) + len(c) > 110:
                    merged.append(cur)
                    cur = c
                else:
                    cur = (cur + " " + c).strip()
            if cur:
                merged.append(cur)
            out.append({"sid": sc["id"], "key": key, "ai": text, "start": caps[i][0] - 0.25})
            i += len(merged)
    if i != len(caps):
        sys.exit("captions.srt does not match narration.py: run assemble.py first or check the files")
    video_end = tl["total_s"] - 4.0          # the end card is the last 4 s
    for b, nxt in zip(out, out[1:] + [{"start": video_end}]):
        b["window"] = nxt["start"] - b["start"]
    return out, tl


def build():
    beats, tl = beat_windows()
    spoken = {(s, k): t for s, gs in C.items() for _, ls in gs for k, t in ls}
    order = [(b["sid"], b["key"]) for b in beats]
    flat = [(s, k) for s, gs in C.items() for _, ls in gs for k, _ in ls]
    if flat != order:
        sys.exit("speaker_content.py beats are not the same, in the same order, as narration.py")
    bad = []
    for b in beats:
        text = spoken[(b["sid"], b["key"])]
        b["text"], b["words"] = text, len(text.split())
        b["talk"] = b["window"] - OVERHEAD
        b["wpm"] = b["words"] / b["talk"] * 60
        b["slack"] = b["talk"] - b["words"] * 60 / MAX_WPM
        if b["wpm"] > MAX_WPM:
            bad.append(b)
    if bad:
        for b in bad:
            print(f"TOO FAST {b['sid']}/{b['key']}: {b['words']} words in {b['talk']:.1f}s = {b['wpm']:.0f} wpm: {b['text']}")
        sys.exit(1)

    seen = set()

    def hinted(text):
        for pat, hint in HINTS:
            if pat in seen:
                continue
            m = re.search(pat, text)
            if m:
                seen.add(pat)
                text = text[:m.end()] + f" [{hint}]" + text[m.end():]
        return text

    scenes = []
    for sc in narration.SCENES:
        sid = sc["id"]
        mine = [b for b in beats if b["sid"] == sid]
        t0, t1 = tl["starts"][sid], tl["ends"][sid]
        words = sum(b["words"] for b in mine)
        groups = []
        for cue, ls in C[sid]:
            items = []
            for k, _ in ls:
                b = next(x for x in mine if x["key"] == k)
                cut = "full" if b["start"] >= CUT else ("part" if b["start"] + b["window"] > CUT else "")
            items.append({"start": b["start"], "text": hinted(b["text"]), "limit": LIMITS.get((sid, k)), "cut": cut,
                              "pause": int(b["slack"]) if b["slack"] >= PAUSE_MIN else 0})
            groups.append((cue, items))
        scenes.append({"sid": sid, "n": int(sid[1:]), "title": re.sub(r"^Scene \d+ - ", "", sc["title"]), "t0": t0, "t1": t1,
                       "secs": t1 - t0, "words": words, "wpm": words / (t1 - t0) * 60,
                       "fast": max(b["wpm"] for b in mine), "groups": groups})
    return scenes, tl, beats


def sheet_lines(scenes, beats):
    lim = {}
    for b in beats:
        if (b["sid"], b["key"]) in LIMITS:
            lim[(b["sid"], b["key"])] = b
    return lim


def write_md(scenes, tl, beats):
    L = ["# Speaker script - GeoLegalVault demo v2", "",
         "Read this while watching `GeoLegalVault_Demo_v2_silent_captions.mp4`. Timestamps are positions on that video "
         "(the same as `GeoLegalVault_Demo_v2.mp4`). A sentence's picture appears at its timestamp; start speaking "
         "about a quarter of a second after it. Text in [square brackets] is a hint and is **not read aloud**. "
         f"Every sentence is trimmed to fit at {MAX_WPM} words per minute or less.", "",
         "---", "", "## Before you record (one page)", "", "### Scenes", "",
         "| # | Scene | Start - end | Seconds | Words | Avg wpm | Fastest sentence |", "|---|---|---|---|---|---|---|"]
    L.append("| 0 | Title slide (your scene00 recording) | 0:00 - 0:24 | 24 | - | - | - |")
    for s in scenes:
        L.append(f"| {s['n']} | {s['title']} | {fmt(s['t0'])} - {fmt(s['t1'])} | {s['secs']:.0f} | {s['words']} | {s['wpm']:.0f} | {s['fast']:.0f} |")
    tot_w = sum(s["words"] for s in scenes)
    L += ["", "**Final video:** it starts with a 24-second title slide, so every main-video timestamp in this script is "
          f"**+{SHIFT} s** in `GeoLegalVault_Demo_v2_final.mp4` (exactly 23.98 s when the title clip is 24.48 s; add it to the time shown here). "
          "The video is cut at **19:28** of the main video, so what follows is marked **CUT - don't record**: the last part of "
          "scene 18's first sentence, and all of its other sentences (scene 18 is almost entirely cut). A 3-second thank-you slide follows.", "",
          f"Total: {tl['total_s'] / 60:.1f} minutes of video, {tot_w} spoken words. The first 4 seconds and the last 4 seconds "
          "are title/end cards with no speech. Avg wpm counts the whole scene including pauses; the real pace while "
          "you speak is the 'fastest sentence' figure or lower.", "", "### Key terms to be able to explain", ""]
    L += [f"- **{a}**: {b}" for a, b in TERMS]
    L += ["", "### Three honest limits - do not skip", ""]
    lim = sheet_lines(scenes, beats)
    names = {("s01", "b5"): "1. Tamper-evident, not tamper-proof", ("s05", "k6"): "2. Geofence is policy, not guaranteed location",
             ("s16", "k10"): "3. The audit log has no hash chain yet"}
    for key, name in names.items():
        b = lim[key]
        L.append(f"- **{name}** - {fmt(b['start'])}, scene {int(key[0][1:])}: \"{b['text']}\"")
    L += ["- The closing summary of limits (scene 18, 19:29) is after the 19:28 cut, so in the **final** video these three, said earlier, are the only places the limits are stated. In the uncut video it repeats them.",
          "- Say: prototype, Sepolia test network, tamper-evident, policy-level geofencing. Never say: tamper-proof, "
          "unhackable, guaranteed location. The app has no rejected state: say \"changes requested\".", "",
          "---", "",
          "## Scene 0 - Title slide", "",
          "**Final video only:** 0:00 - 0:24 (24 seconds; your recording `scene00.wav` is 24.48 s). The slide shows the project, "
          "the three team members, the course and the faculty. Suggested wording (about 40 words, easy at 130 wpm); "
          "skip this if your scene00.wav is already recorded:", "",
          "> **ON SCREEN:** Title slide: GeoLegalVault, team members, course details", "",
          f"- `0:00` {SCENE0}", "", "---", ""]
    for s in scenes:
        L += [f"## Scene {s['n']} - {s['title']}", "",
              f"**Silent video:** {fmt(s['t0'])} - {fmt(s['t1'])} ({s['secs']:.0f} seconds available) | "
              f"{s['words']} words | about {s['wpm']:.0f} words per minute over the scene, fastest sentence {s['fast']:.0f}", ""]
        for cue, items in s["groups"]:
            L += [f"> **ON SCREEN:** {cue}", ""]
            for it in items:
                tag = f" **★ MUST SAY ({it['limit']})**" if it["limit"] else ""
                if it["cut"] == "full":
                    tag += " **CUT - don't record**"
                elif it["cut"] == "part":
                    tag += " **ENDS AT 19:28 - the final video cuts here; the voice fades out. Say it at your normal pace, the last words are cut**"
                L.append(f"- `{fmt(it['start'])}` {it['text']}{tag}")
                if it["pause"]:
                    L.append(f"  - **[PAUSE {it['pause']}s]** the video holds here, no narration")
            L.append("")
        L.append("---")
        L.append("")
    (ROOT / "SPEAKER_SCRIPT.md").write_text("\n".join(L), encoding="utf-8")


def write_txt(scenes, tl, beats):
    W = 58
    out = []

    def add(s="", gap=True):
        for ln in (textwrap.wrap(s, W) or [""]):
            out.append(ln)
            out.append("")          # blank line after every line = large line spacing

    def rule():
        out.extend(["=" * W, "", ""])

    add("GEOLEGALVAULT DEMO V2 - SPEAKER SCRIPT")
    add(f"Read over GeoLegalVault_Demo_v2_silent_captions.mp4. Times are m:ss on that video. Text in [brackets] is a hint, do not read it aloud. Start speaking a quarter of a second after the time.")
    rule()
    add("BEFORE YOU RECORD")
    for s in scenes:
        add(f"Scene {s['n']}: {s['title']} - {fmt(s['t0'])} to {fmt(s['t1'])} ({s['secs']:.0f} s, fastest {s['fast']:.0f} wpm)")
    add("")
    add("FINAL VIDEO: a 24 second title slide comes first, so every main-video time in this script is 24 seconds LATER in the final video. The video is cut at 19:28 of the main video: anything marked CUT - DO NOT RECORD is not used.")
    add("Scene 0: Title slide - 0:00 to 0:24 (suggested words below)")
    add("")
    add("KEY TERMS")
    for a, b in TERMS:
        add(f"{a}: {b}")
    add("")
    add("THREE HONEST LIMITS - DO NOT SKIP")
    lim = sheet_lines(scenes, beats)
    for n, key in enumerate([("s01", "b5"), ("s05", "k6"), ("s16", "k10")], 1):
        b = lim[key]
        add(f"{n}. At {fmt(b['start'])}: {b['text']}")
    add("Say: prototype, Sepolia test network, tamper-evident, policy-level geofencing. Never say: tamper-proof, unhackable, guaranteed location.")
    rule()
    add("SCENE 0: TITLE SLIDE")
    add("0:00 to 0:24 (final video only)")
    add("ON SCREEN: Title slide: GeoLegalVault, team members, course details")
    add(f"0:00   {SCENE0}")
    rule()
    for s in scenes:
        add(f"SCENE {s['n']}: {s['title'].upper()}")
        add(f"{fmt(s['t0'])} to {fmt(s['t1'])}  ({s['secs']:.0f} seconds)")
        out.append("")
        for cue, items in s["groups"]:
            add(f"ON SCREEN: {cue}")
            for it in items:
                tag = "   *** MUST SAY ***" if it["limit"] else ""
                if it["cut"] == "full":
                    tag += "   *** CUT - DO NOT RECORD ***"
                elif it["cut"] == "part":
                    tag += "   *** ENDS AT 19:28: the video cuts here, the voice fades out ***"
                add(f"{fmt(it['start'])}   {it['text']}{tag}")
                if it["pause"]:
                    add(f"[PAUSE {it['pause']} seconds - no narration]")
            out.append("")
        rule()
    (ROOT / "SPEAKER_SCRIPT.txt").write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    sc, tl, beats = build()
    write_md(sc, tl, beats)
    write_txt(sc, tl, beats)
    print(f"wrote SPEAKER_SCRIPT.md and SPEAKER_SCRIPT.txt: {sum(s['words'] for s in sc)} words, "
          f"fastest sentence {max(s['fast'] for s in sc):.0f} wpm")
