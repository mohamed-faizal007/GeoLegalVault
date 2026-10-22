"""Assemble the final videos from recordings/ + audio/.

    demo_video/.venv/Scripts/python.exe demo_video2/assemble.py [--scenes s02,s03]   (default: everything recorded)

Sync model (see scenes/common.py): every spoken sentence is one "beat" with wall-clock start/end recorded while the
scene ran. Here each beat is cut from its role's video (long waits trimmed), held at least as long as its sentence
(last frame frozen if shorter), and its audio is placed at the beat's start. Beats concatenate in narration order, so
picture and voice agree sentence by sentence for the whole video, not scene by scene.

Outputs (gitignored binaries): GeoLegalVault_Demo_v2.mp4 (voice + soft subtitles),
GeoLegalVault_Demo_v2_silent_captions.mp4 (no audio, captions burned in); captions.srt, timeline.json,
NARRATION_SCRIPT.md. Work files go to build/.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

import narration

ROOT = Path(__file__).resolve().parent
REC, AUD, BLD = ROOT / "recordings", ROOT / "audio", ROOT / "build"
FF = imageio_ffmpeg.get_ffmpeg_exe()
LEAD, GAP = 0.25, 0.45
KEEP_WAIT = 2.0        # seconds of a trimmed wait that stay in the video
MARK_FPS = 20          # frames per second sampled when decoding the sync marker
CARD_SECS = 4.0


def run(*args):
    r = subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", *map(str, args)], capture_output=True, text=True)
    if r.returncode:
        sys.exit("ffmpeg failed: " + r.stderr[-1200:])


def duration(path: Path) -> float:
    out = subprocess.run([FF, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])


CSS = """body{margin:0;width:1920px;height:1080px;background:linear-gradient(135deg,#0b1020,#1a1f4a);color:#fff;
font-family:'Segoe UI',Arial,sans-serif;display:flex;flex-direction:column;justify-content:center;padding:0 140px;box-sizing:border-box}
h1{font-size:88px;margin:0 0 40px}li{font-size:46px;line-height:1.45;margin-bottom:14px;color:#dbe6ff}ul{padding-left:44px}
.f{position:absolute;bottom:40px;left:140px;font-size:26px;color:#8fa6d9}"""


def render_slides():
    BLD.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        for key, (title, bullets) in narration.SLIDES.items():
            big = key in ("title", "end")
            lis = "".join(f"<li>{x}</li>" for x in bullets)
            body = (f"<h1 style='font-size:120px'>{title}</h1><ul style='list-style:none;padding:0'>{lis}</ul>" if big
                    else f"<h1>{title}</h1><ul>{lis}</ul>")
            pg.set_content(f"<html><style>{CSS}</style><body>{body}<div class=f>GeoLegalVault prototype | Ethereum Sepolia TESTNET | tamper-evident, policy-level geofencing</div></body></html>")
            pg.screenshot(path=str(BLD / f"slide_{key}.png"))
        b.close()


_MARKS: dict = {}


def decode_marks(webm: Path) -> dict:
    """seq -> first video time (s) at which the sync marker (bottom-right, see scenes/common.py) shows that number."""
    if webm in _MARKS:
        return _MARKS[webm]
    r = subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-i", str(webm), "-vf",
                        f"fps={MARK_FPS},crop=224:16:1600:1064,scale=14:1:flags=area,format=gray", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                       capture_output=True)
    raw, first = r.stdout, {}
    for i in range(len(raw) // 14):
        v = raw[i * 14:(i + 1) * 14]
        if v[0] - v[13] < 70:           # sync squares (white, black) missing: page between documents
            continue
        thr = (v[0] + v[13]) / 2
        n = 0
        for x in v[1:13]:
            n = n * 2 + (1 if x > thr else 0)
        if n and n not in first:
            first[n] = i / MARK_FPS
    _MARKS[webm] = first
    return first


def load_beats() -> dict:
    """(sid, key) -> (beat, recording dir) from the latest recording that has it."""
    best = {}
    for tl in sorted(REC.glob("*/timeline.json")):
        data = json.loads(tl.read_text())
        for b in data["beats"]:
            k = (b["sid"], b["key"])
            if k not in best or b["t0"] > best[k][0]["t0"]:
                best[k] = (b, tl.parent, data.get("t_close"), data["beats"])
    return best


_CAPS: dict = {}


def caption_changes(webm: Path) -> list:
    """Video times at which the caption bar text changes (used only for recordings made before the sync marker existed)."""
    if webm not in _CAPS:
        out = subprocess.run([FF, "-hide_banner", "-i", str(webm), "-vf", "crop=1920:40:0:1030,select='gt(scene,0.008)',showinfo",
                              "-f", "null", "-"], capture_output=True, text=True).stderr
        _CAPS[webm] = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", out)]
    return _CAPS[webm]


def legacy_intervals(b, rec_dir, t_close, all_beats):
    """Recordings from before the sync marker: predict each beat's video time from the wall clock (end-aligned), then
    snap to the nearest caption change that the video really shows."""
    src = rec_dir / f"{b['role']}.webm"
    dv = duration(src)
    pred = lambda t: dv - (t_close[b["role"]] - t)
    ch = caption_changes(src)
    own = sorted((x for x in all_beats if x["role"] == b["role"]), key=lambda x: x["t0"])
    used, snap = set(), {}
    for x in own:
        cands = [(abs(c - pred(x["t0"])), c) for c in ch if abs(c - pred(x["t0"])) < 4.0 and c not in used]
        if cands:
            _, c = min(cands)
            used.add(c)
            snap[x["key"]] = c
    s0 = snap.get(b["key"], pred(b["t0"]))
    print(f"   legacy {b['sid']}/{b['key']}: predicted {pred(b['t0']):.2f} snapped {s0:.2f} (shift {s0 - pred(b['t0']):+.2f}s)")
    cuts, cur = [], s0
    for w0, w1 in sorted(b["waits"]):
        if w1 - w0 > KEEP_WAIT + 0.5:
            cuts.append((cur, s0 + (w0 - b["t0"]) + KEEP_WAIT))
            cur = s0 + (w1 - b["t0"]) - 0.3
    cuts.append((cur, s0 + (b["t1"] - b["t0"])))
    return src, [(x, y) for x, y in cuts if y > x + 0.04]


def intervals(b, rec_dir, t_close=None, all_beats=None):
    """Source intervals (seconds in the role's webm) for this beat, read from the sync markers, waits trimmed."""
    if "seq0" not in b:
        return legacy_intervals(b, rec_dir, t_close, all_beats)
    src = rec_dir / f"{b['role']}.webm"
    t = decode_marks(src)
    found = sorted(t)

    def T(seq):
        """Time of a marker; a marker that no frame caught is replaced by the next one that was (they follow each other)."""
        nxt = [x for x in found if x >= seq]
        if not nxt:
            sys.exit(f"no sync marker >= {seq} in {src} for {b['sid']}/{b['key']}")
        return t[nxt[0]]

    cuts, cur = [], T(b["seq0"])
    for w0, w1 in sorted(b["waits"]):
        if T(w1) - T(w0) > KEEP_WAIT + 0.5:
            cuts.append((cur, T(w0) + KEEP_WAIT))
            cur = T(w1) - 0.3
    cuts.append((cur, T(b["seq1"])))
    return src, [(x, y) for x, y in cuts if y > x + 0.04]


def main():
    only = None
    if "--scenes" in sys.argv:
        only = set(sys.argv[sys.argv.index("--scenes") + 1].split(","))
    if BLD.exists():
        shutil.rmtree(BLD)
    render_slides()
    beats = load_beats()
    segs, wavs = [], []          # video segment files, per-beat audio files (same total length)
    clock = 0.0
    caps, starts, ends, beat_times = [], {}, {}, {}

    def card(key, secs):
        out = BLD / f"card_{key}.mp4"
        run("-loop", "1", "-i", BLD / f"slide_{key}.png", "-t", secs, "-vf", "fps=30,format=yuv420p", "-an",
            "-c:v", "libx264", "-crf", "20", out)
        w = BLD / f"card_{key}.wav"
        run("-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", secs, "-c:a", "pcm_s16le", w)
        segs.append(out); wavs.append(w)

    card("title", CARD_SECS); clock += CARD_SECS
    n = 0
    for sc in narration.SCENES:
        sid = sc["id"]
        if only and sid not in only:
            continue
        starts[sid] = clock
        for key, text in sc["lines"]:
            if (sid, key) not in beats:
                sys.exit(f"missing recording for {sid}/{key}")
            b, rec_dir, t_close, all_beats = beats[(sid, key)]
            wav = AUD / f"{sid}_{key}.wav"
            d = duration(wav)
            need = LEAD + d + GAP
            out = BLD / f"b{n:03d}.mp4"
            if b.get("slide"):
                run("-loop", "1", "-i", BLD / f"slide_{sid}_{b['slide']}.png", "-t", f"{need:.3f}",
                    "-vf", "fps=30,format=yuv420p", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", out)
                length = need
            else:
                src, ivs = intervals(b, rec_dir, t_close, all_beats)
                natural = sum(y - x for x, y in ivs)
                length = max(natural, need)
                parts = []
                for i, (x, y) in enumerate(ivs):
                    p = BLD / f"b{n:03d}_{i}.mp4"
                    last = i == len(ivs) - 1
                    pad = (length - natural) if last else 0.0
                    vf = "fps=30,scale=1920:1080:flags=lanczos,setsar=1,drawbox=x=1596:y=1060:w=232:h=20:color=0x080c18:t=fill,format=yuv420p"
                    if pad > 0.01:
                        vf += f",tpad=stop_mode=clone:stop_duration={pad:.3f}"
                    run("-ss", f"{x:.3f}", "-i", src, "-t", f"{(y - x) + pad:.3f}", "-vf", vf, "-an",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", p)
                    parts.append(p)
                if len(parts) == 1:
                    parts[0].replace(out)
                else:
                    lst = BLD / f"b{n:03d}.txt"
                    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
                    run("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out)
            aw = BLD / f"b{n:03d}.wav"
            run("-i", wav, "-af", f"adelay={int(LEAD * 1000)}|{int(LEAD * 1000)},apad=whole_dur={length:.3f},aresample=48000,aformat=channel_layouts=stereo",
                "-t", f"{length:.3f}", "-c:a", "pcm_s16le", aw)
            segs.append(out); wavs.append(aw)
            # captions: the sentence is shown while it is spoken, split into <=110-char chunks by character share
            chunks = [c.strip() for c in re.split(r"(?<=[.,:;?!])\s+", text) if c.strip()]
            merged, cur = [], ""
            for c in chunks:
                if cur and len(cur) + len(c) > 110:
                    merged.append(cur); cur = c
                else:
                    cur = (cur + " " + c).strip()
            if cur:
                merged.append(cur)
            tot = sum(len(c) for c in merged) or 1
            t = clock + LEAD
            for c in merged:
                span = d * len(c) / tot
                caps.append((t, t + span, c)); t += span
            beat_times[(sid, key)] = f"{int(clock // 60)}:{int(clock % 60):02d}"
            clock += length
            n += 1
        ends[sid] = clock
        print(f"{sid}: {(ends[sid] - starts[sid]):.0f}s", flush=True)
    card("end", CARD_SECS); clock += CARD_SECS

    def concat(files, out, codec):
        lst = BLD / (out.stem + "_list.txt")
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in files))
        run("-f", "concat", "-safe", "0", "-i", lst, *codec, out)

    vid, aud = BLD / "video.mp4", BLD / "audio.wav"
    concat(segs, vid, ["-c", "copy"])
    concat(wavs, aud, ["-c", "copy"])
    joined = BLD / "joined.mp4"
    run("-i", vid, "-i", aud, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", joined)

    def ts(x):
        h, r = divmod(x, 3600); m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")

    srt = "\n".join(f"{i}\n{ts(a)} --> {ts(b)}\n{txt}\n" for i, (a, b, txt) in enumerate(caps, 1))
    (ROOT / "captions.srt").write_text(srt, encoding="utf-8")
    out_main = ROOT / "GeoLegalVault_Demo_v2.mp4"
    run("-i", joined, "-i", ROOT / "captions.srt", "-map", "0:v", "-map", "0:a", "-map", "1:0", "-c:v", "copy", "-c:a", "copy",
        "-c:s", "mov_text", "-metadata:s:s:0", "language=eng", out_main)
    style = "FontName=Segoe UI,FontSize=8,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=26"
    srt_path = (ROOT / "captions.srt").as_posix().replace(":", r"\:")
    out_silent = ROOT / "GeoLegalVault_Demo_v2_silent_captions.mp4"
    run("-i", vid, "-vf", f"subtitles='{srt_path}':original_size=1920x1080:force_style='{style}'", "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", out_silent)

    marks = {k: f"{int(starts[k] // 60)}:{int(starts[k] % 60):02d} - {int(ends[k] // 60)}:{int(ends[k] % 60):02d}" for k in starts}
    narration.write_markdown(marks, beat_times)
    (ROOT / "timeline.json").write_text(json.dumps(
        {"starts": starts, "ends": ends, "total_s": clock, "beats": {f"{a}/{b}": t for (a, b), t in beat_times.items()}}, indent=1))
    print(f"TOTAL {clock / 60:.1f} min -> {out_main.name}, {out_silent.name}")


if __name__ == "__main__":
    main()
