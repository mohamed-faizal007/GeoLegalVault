"""replace_voice.py b --final: your own voice on every scene, in sync, by stretching the PICTURE (never the voice).

Per scene (scene01.wav .. scene18.wav in the voice folder):
  * the silence before your first word is trimmed down to 0.15 s (only with --trim-silence), and the silence after your
    last word to 0.35 s (scene 18: 0.5 s, it ends the main video); voice is never cut. A file whose voice runs right up to
    its last sample is kept whole and flagged.
  * all scenes get the same loudness (gain per scene, then a peak limiter); no denoising.
  * the scene's slice of the silent video is used as it is when your audio is shorter; when it is longer, the last frame is
    held for the overrun, so every later scene still starts together with your voice.
Then: title slide + scene00 voice, the main part (ends 0.5 s after your last word in scene 18), 3 s thank-you slide.
No subtitle track unless --captions. Needs only ffmpeg; writes new files (the video and <video>.report.json).
"""
import json
import sys
import tempfile
from pathlib import Path

TARGET_LUFS = -20.6      # same loudness as the AI narration in GeoLegalVault_Demo_v2_final.mp4
LEAD = 0.15              # voice starts this long after the scene's first frame
TAIL = 0.35              # silence kept after your last spoken word
SCENE18_TAIL = 0.5


def _scene18_hold_limit(ROOT, starts):
    """Seconds into scene 18 where the slide of its second sentence begins (the first sentence's slide is held until then)."""
    srt = ROOT / "captions.srt"
    if srt.exists():
        for blk in srt.read_text(encoding="utf-8").strip().split("\n\n"):
            ln = blk.split("\n")
            if ln[2].startswith("Honest limits"):
                h, m, s = ln[1].split(" --> ")[0].replace(",", ".").split(":")
                return int(h) * 3600 + int(m) * 60 + float(s) - 0.30 - starts["s18"]
    return None


def mode_b_final(args):
    import final_cut as fc
    import replace_voice as rv
    ROOT, SR, run = rv.ROOT, rv.SR, rv.run
    tl = json.loads((ROOT / "timeline.json").read_text())
    starts, ends = tl["starts"], tl["ends"]
    vdir = Path(args.voice_dir)
    if not vdir.is_absolute():
        vdir = ROOT / vdir
    video = rv.pick_video(args)
    out = rv.resolve_output(args)
    title, thanks = Path(args.title_slide), Path(args.thanks_slide)
    for p in (title, thanks):
        if not p.exists():
            sys.exit(f"slide image not found: {p}")

    def find(n):
        return next((vdir / f"scene{n:02d}{e}" for e in rv.AUDIO_EXT if (vdir / f"scene{n:02d}{e}").exists()), None)

    if not find(0):
        sys.exit(f"--final needs scene00.wav (the title slide voice) in {vdir}")
    hold18 = _scene18_hold_limit(ROOT, starts)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        rows = []
        # 1. analyse and clean every scene file
        for n in range(1, 19):
            sid, src = f"s{n:02d}", find(n)
            row = {"scene": n, "pic_src": ends[sid] - starts[sid], "file": src.name if src else None}
            if n == 18 and hold18:
                row["pic_src"] = hold18
            if not src:
                rows.append(row)
                continue
            a = fc.analyze(src, tmp)
            tail = SCENE18_TAIL if n == 18 else TAIL
            runs_to_end = a["last"] >= a["dur"] - 0.15
            lead_cut = max(a["first"] - LEAD, 0.0) if args.trim_silence else 0.0
            end = a["dur"] if runs_to_end else min(a["dur"], a["last"] + tail)
            length = end - lead_cut
            stereo = tmp / f"s{n:02d}_st.wav"
            run("-ss", f"{lead_cut:.3f}", "-t", f"{length:.3f}", "-i", src, "-vn", "-af",
                f"aresample={SR},pan=stereo|c0=c0|c1=c0", "-c:a", "pcm_s16le", stereo)
            gain = TARGET_LUFS - fc.lufs(stereo)
            clean = tmp / f"s{n:02d}_clean.wav"
            run("-i", stereo, "-af", f"volume={gain:.2f}dB,alimiter=limit=0.89:level=disabled,aformat=channel_layouts=stereo",
                "-c:a", "pcm_s16le", clean)
            row.update(wav=clean, file_dur=a["dur"], voice_start=a["first"] - lead_cut, voice_end=a["last"] - lead_cut,
                       length=length, gain=gain, floor_raw=a["floor"], floor_after=a["floor"] + gain,
                       snr=a["speech"] - a["floor"], gaps=a["gaps"], runs_to_end=runs_to_end, lead_cut=lead_cut)
            rows.append(row)
            print(f"scene {n:2d} analysed", flush=True)
        # 2. picture
        segs = []

        def cut(name, a, b, pad=0.0):
            f = tmp / f"{name}.mp4"
            vf = "fps=30,scale=1920:1080:flags=lanczos,setsar=1,format=yuv420p"
            if pad > 0.01:
                vf += f",tpad=stop_mode=clone:stop_duration={pad:.3f}"
            run("-ss", f"{a:.3f}", "-i", video, "-t", f"{(b - a) + pad:.3f}", "-vf", vf, "-an",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", f)
            segs.append(f)
            return fc.duration(f)

        pos = cut("seg00", 0.0, starts["s01"])         # the 4 s opening card of the main video
        for row in rows:
            n = row["scene"]
            a, avail, have = starts[f"s{n:02d}"], row["pic_src"], row.get("length", 0.0)
            row["main_start"] = pos
            if n == 18:
                want = have if have else avail
                row["pad"] = max(0.0, want - avail)
                d = cut(f"seg{n:02d}", a, a + min(want, avail), pad=row["pad"])
            else:
                row["pad"] = max(0.0, have - avail)
                d = cut(f"seg{n:02d}", a, a + avail, pad=row["pad"])
            row["pic_len"] = d
            pos += d
            print(f"scene {n:2d} picture {d:.1f}s", flush=True)
        main_len = pos
        lst = tmp / "segs.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in segs))
        main_v = tmp / "main_ext.mp4"
        run("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", main_v)
        # 3. voice, each scene at its picture's start
        have = [r for r in rows if r.get("wav")]
        inputs, filt, labels = [], [], []
        for i, r in enumerate(have):
            inputs += ["-i", r["wav"]]
            ms = int(round(r["main_start"] * 1000))
            filt.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
            labels.append(f"[a{i}]")
        filt.append("".join(labels) + f"amix=inputs={len(have)}:normalize=0:duration=longest[mix]")
        mix = tmp / "mix.wav"
        run(*inputs, "-filter_complex", ";".join(filt), "-map", "[mix]", "-ac", "2", "-ar", str(SR), "-c:a", "pcm_s16le", mix)
        # 4. title voice at the same loudness, then title + main + thank-you
        s00 = tmp / "s00_raw.wav"
        run("-i", find(0), "-vn", "-ar", str(SR), "-c:a", "pcm_s16le", s00)
        t00 = tmp / "s00_title.wav"
        g00 = fc.title_audio(s00, t00, TARGET_LUFS)
        srt = None
        if args.captions:
            srt = ROOT / "captions_final.srt"
            if not srt.exists():
                fc.shift_captions(ROOT / "captions.srt", srt, fc.duration(t00) - fc.XFADE)
        T, start, total = fc.compose(main_video=main_v, main_audio=mix, title_png=title, thanks_png=thanks,
                                     title_wav=t00, out=out, subs=srt, cut=main_len)
    print(f"\nscene00: {T:.2f}s title voice, gain {g00:+.1f} dB (target {TARGET_LUFS} LUFS)")
    print("scene | picture s | audio s | overrun/gap | held s | gain dB | noise floor after | SNR dB | voice starts | flags")
    report = []
    for r in rows:
        n = r["scene"]
        if not r.get("wav"):
            print(f"{n:5d} | no file")
            continue
        flags = []
        if r["floor_after"] > -50:
            flags.append("HISS?")
        if r["snr"] < 35:
            flags.append("low SNR")
        if r["runs_to_end"]:
            flags.append("voice runs to the end of the file (last word clipped?)")
        print(f"{n:5d} | {r['pic_src']:9.1f} | {r['length']:7.1f} | {r['length'] - r['pic_src']:+8.1f}s | {r['pad']:5.1f}  | "
              f"{r['gain']:+6.1f}  | {r['floor_after']:6.1f} dBFS | {r['snr']:5.0f} | {r['voice_start']:.2f}s | {', '.join(flags)}")
        d = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items() if k != "wav"}
        d["final_start"] = round(start + r["main_start"], 3)
        report.append(d)
    out.with_suffix(".report.json").write_text(json.dumps(report, indent=1, default=str))
    print(f"\nmain part {main_len:.2f}s; total video {total:.2f}s ({int(total // 60)}:{total % 60:05.2f})")
    print(f"WROTE {out}\nreport: {out.with_suffix('.report.json')}")
