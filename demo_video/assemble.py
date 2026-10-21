"""Assemble the final videos from recordings/ + audio/. Run: demo_video/.venv/Scripts/python.exe demo_video/assemble.py

Outputs (gitignored binaries): GeoLegalVault_Demo.mp4, GeoLegalVault_Demo_silent_captions.mp4; and captions.srt,
timeline.json, plus NARRATION_SCRIPT.md with timestamps. Work files go to build/.
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
REC = ROOT / "recordings"
AUD = ROOT / "audio"
BLD = ROOT / "build"
FF = imageio_ffmpeg.get_ffmpeg_exe()
LEAD = 0.5   # seconds of picture before the voice starts
TAIL = 1.2   # seconds of picture after the voice ends

# (scene_dir, file, t_start, t_end, video_offset): t = timeline time of the scene script; video time = t - offset
V = lambda d, f, a, b, off, w=1: ("vid", d, f, a, b, off, w)
I = lambda key, w=1: ("img", key, w)

PLAN = {
    "s01": [I("s01a"), I("s01b")],
    "s02": [V("scene02_login_roles", "staff", 1.8, 18.0, 1.2), V("scene02_login_roles", "legal", 14.6, 25.0, 14.0),
            V("scene02_login_roles", "admin", 23.6, 45.5, 23.0)],
    "s03": [V("scene03_admin", "admin", 3.0, 8.2, 1.0, 0.3), V("scene03_admin", "admin", 8.2, 13.8, 1.0, 4), V("scene03_admin", "admin", 13.8, 30.5, 1.0, 1),
            V("scene03b_lockout", "viewer", 1.4, 10.2, 0.8, 0.5), V("scene03b_lockout", "viewer", 19.7, 34.5, 0.8, 0.5)],
    "s04": [V("scene04_upload", "staff", 3.0, 22.1, 0.9), V("scene04_upload", "staff", 22.1, 41.0, 0.9, 2),
            V("scene04_upload", "staff", 41.5, 52.5, 0.9), V("scene04b_hash_storage", "staff", 3.0, 17.4, 1.1),
            V("scene04b_hash_storage", "staff", 17.4, 29.5, 1.1)],
    "s05": [V("scene05_geofence_denied", "staff", 6.0, 29.7, 1.0), V("scene05_geofence_denied", "staff", 29.7, 48.0, 1.0),
            V("scene05_geofence_denied", "staff", 48.0, 60.0, 1.0)],
    "s06": [V("scene06a_maker_checker", "legal", 4.0, 17.2, 1.0), V("scene06a_maker_checker", "reviewer", 24.5, 38.0, 17.3),
            V("scene06a_maker_checker", "legal", 52.3, 62.0, 1.0), V("scene06a2_selfapprove_api", "legal", 15.6, 26.0, 1.0),
            V("scene06b_approve", "legal", 14.3, 22.0, 5.8), V("scene06b_approve", "legal", 34.0, 43.5, 5.8)],
    "s07": [V("scene07_anchor", "legal", 10.6, 24.0, 1.1), V("scene07_anchor", "legal", 24.0, 32.6, 1.1),
            V("scene07_anchor", "legal", 32.6, 46.0, 1.1), V("scene07_anchor", "legal", 49.4, 63.0, 1.1)],
    "s08": [V("scene08_clearance", "viewer", 8.0, 16.5, 1.2), V("scene08_clearance", "viewer", 22.0, 41.0, 1.2),
            V("scene08_clearance", "viewer", 41.6, 56.0, 1.2)],
    "s09": [V("scene09_verify_ok", "legal", 2.5, 27.5, 1.0)],
    "s10": [V("scene10_tamper", "legal", 6.3, 19.0, 0.8), V("scene10_tamper", "legal", 24.2, 40.0, 0.8),
            V("scene10_tamper", "legal", 40.0, 50.0, 0.8), V("scene10_tamper", "legal", 52.0, 65.5, 0.8)],
    "s11": [V("scene11_not_anchored", "reviewer", 11.1, 28.5, 1.6), I("s11")],
    "s12": [V("scene12_mongo_audit", "auditor", 11.5, 21.0, 1.1), V("scene12_mongo_audit", "auditor", 21.0, 37.6, 1.1),
            V("scene12_mongo_audit", "auditor", 37.6, 55.6, 1.1), V("scene12_mongo_audit", "auditor", 55.6, 75.0, 1.1)],
    "s13": [I("s13a"), I("s13b")],
}


def run(*args):
    r = subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", *map(str, args)], capture_output=True, text=True)
    if r.returncode:
        sys.exit("ffmpeg failed: " + r.stderr[-800:])


def duration(path: Path) -> float:
    out = subprocess.run([FF, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])


CSS = """body{margin:0;width:1920px;height:1080px;background:linear-gradient(135deg,#0b1020,#1a1f4a);color:#fff;
font-family:'Segoe UI',Arial,sans-serif;display:flex;flex-direction:column;justify-content:center;padding:0 140px;box-sizing:border-box}
h1{font-size:88px;margin:0 0 40px}li{font-size:44px;line-height:1.5;margin-bottom:14px;color:#dbe6ff}ul{padding-left:44px}
.f{position:absolute;bottom:40px;left:140px;font-size:26px;color:#8fa6d9}"""


def render_slides():
    BLD.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        for key, (title, bullets) in narration.SLIDES.items():
            big = key in ("title", "end")
            lis = "".join(f"<li>{x}</li>" for x in bullets)
            body = (f"<h1 style='font-size:120px'>{title}</h1>{'<ul style=list-style:none;padding:0>' + lis + '</ul>'}" if big
                    else f"<h1>{title}</h1><ul>{lis}</ul>")
            pg.set_content(f"<html><style>{CSS}</style><body>{body}<div class=f>GeoLegalVault prototype | Ethereum Sepolia TESTNET | tamper-evident, policy-level geofencing</div></body></html>")
            pg.screenshot(path=str(BLD / f"slide_{key}.png"))
        b.close()


def encode_seg(out: Path, src_args: list, dur: float, hold: float):
    vf = "fps=30,scale=1920:1080:flags=lanczos,setsar=1,format=yuv420p"
    if hold > 0.01:
        vf += f",tpad=stop_mode=clone:stop_duration={hold:.3f}"
    run(*src_args, "-t", f"{dur + hold:.3f}", "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", out)


def main():
    if BLD.exists():
        shutil.rmtree(BLD)
    render_slides()
    scene_files, starts, ends = [], {}, {}
    clock = 0.0
    caps = []

    def card(key, secs):
        out = BLD / f"card_{key}.mp4"
        run("-loop", "1", "-i", BLD / f"slide_{key}.png", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", secs,
            "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-shortest", out)
        return out

    scene_files.append(card("title", 5)); starts["title"] = 0.0; clock += 5

    for sc in narration.SCENES:
        sid = sc["id"]
        wav = AUD / f"{sid}.wav"
        nd = duration(wav)
        segs = []
        for s in PLAN[sid]:
            if s[0] == "vid":  # clamp to the real clip length so holds are computed from what exists
                src_len = duration(REC / s[1] / f"{s[2]}.webm")
                s = (s[0], s[1], s[2], s[3], min(s[4], s[5] + src_len - 0.15), s[5], s[6])
            segs.append(s)
        # natural lengths
        nat = []
        for s in segs:
            nat.append((s[4] - s[3]) if s[0] == "vid" else None)
        n_img = sum(1 for x in nat if x is None)
        total_target = nd + LEAD + TAIL
        vid_total = sum(x for x in nat if x is not None)
        if n_img:
            img_each = max(8.0, (total_target - vid_total) / n_img)
        else:
            img_each = 0
        base = [x if x is not None else img_each for x in nat]
        deficit = max(0.0, total_target - sum(base))
        ws = [(x[6] if x[0] == 'vid' else x[2]) for x in segs]
        wsum = sum(ws) or 1
        holds = [deficit * w / wsum for w in ws]
        hold_each = deficit / len(segs)
        parts = []
        for i, s in enumerate(segs):
            out = BLD / f"{sid}_{i}.mp4"
            if s[0] == "vid":
                _, d, f, t0, t1, off, _w = s
                src = REC / d / f"{f}.webm"
                vt0 = max(0.0, t0 - off)
                encode_seg(out, ["-i", src, "-ss", f"{vt0:.3f}"], base[i], holds[i])
            else:
                encode_seg(out, ["-loop", "1", "-i", BLD / f"slide_{s[1]}.png"], base[i], holds[i])
            parts.append(out)
        lst = BLD / f"{sid}_list.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
        vid = BLD / f"{sid}_video.mp4"
        run("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", vid)
        vd = duration(vid)
        final = BLD / f"{sid}.mp4"
        run("-i", vid, "-i", wav, "-filter_complex", f"[1:a]adelay={int(LEAD*1000)}|{int(LEAD*1000)},apad,aresample=48000,aformat=channel_layouts=stereo[a]",
            "-map", "0:v", "-map", "[a]", "-t", f"{vd:.3f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", final)
        scene_files.append(final)
        starts[sid] = clock
        # captions: split spoken text into sentences, time by character share
        text = narration.spoken(sc)
        sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]
        tot = sum(len(x) for x in sents)
        t = clock + LEAD
        for x in sents:
            span = nd * len(x) / tot
            caps.append((t, t + span, x))
            t += span
        clock += vd
        ends[sid] = clock
        print(f"{sid}: video {vd:.1f}s narration {nd:.1f}s (holds {hold_each:.1f}s each)")

    scene_files.append(card("end", 5)); clock += 5

    lst = BLD / "all.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in scene_files))
    joined = BLD / "joined.mp4"
    run("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined)

    def ts(x):
        h, r = divmod(x, 3600); m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")
    srt = "\n".join(f"{i}\n{ts(a)} --> {ts(b)}\n{txt}\n" for i, (a, b, txt) in enumerate(caps, 1))
    (ROOT / "captions.srt").write_text(srt, encoding="utf-8")

    # Main video: voice + soft subtitle track (mov_text) so players can toggle captions.
    out_main = ROOT / "GeoLegalVault_Demo.mp4"
    run("-i", joined, "-i", ROOT / "captions.srt", "-map", "0:v", "-map", "0:a", "-map", "1:0", "-c:v", "copy", "-c:a", "copy",
        "-c:s", "mov_text", "-metadata:s:s:0", "language=eng", out_main)
    # Silent version with captions burned in (above the app's own caption bar), for recording your own voice.
    style = "FontName=Segoe UI,FontSize=8,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=26"
    srt_path = (ROOT / "captions.srt").as_posix().replace(":", r"\:")
    out_silent = ROOT / "GeoLegalVault_Demo_silent_captions.mp4"
    run("-i", joined, "-vf", f"subtitles='{srt_path}':original_size=1920x1080:force_style='{style}'", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", out_silent)

    marks = {k: f"{int(starts[k] // 60)}:{int(starts[k] % 60):02d} - {int(ends[k] // 60)}:{int(ends[k] % 60):02d}" for k in starts if k != "title"}
    narration.write_markdown(marks)
    (ROOT / "timeline.json").write_text(json.dumps({"starts": starts, "ends": ends, "total_s": clock}, indent=1))
    print(f"TOTAL {clock/60:.1f} min -> {out_main.name}, {out_silent.name}")


if __name__ == "__main__":
    main()
