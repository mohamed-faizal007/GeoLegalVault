"""Put your own voice on the silent GeoLegalVault demo video. Writes a NEW file; never touches the AI-voice videos.

Mode A - one continuous recording made while the silent video played:
    python demo_video2/replace_voice.py a --audio my_voice_full.m4a [--offset 1.5] [--normalize] [--trim-silence]

Mode B - one file per scene in demo_video2/my_voice/ (scene01.wav ... scene18.wav; .mp3/.m4a/.flac also work):
    python demo_video2/replace_voice.py b [--voice-dir my_voice] [--offset 0] [--normalize] [--trim-silence]

Common options: --output PATH (default demo_video2/GeoLegalVault_Demo_v2_my_voice.mp4), --video PATH.

--offset N shifts your voice later by N seconds (negative = earlier, i.e. cut the first N seconds).
--trim-silence removes silence at the start of each recording (Mode A: of the file; Mode B: of each scene file).
--normalize evens out the loudness (EBU R128, about -16 LUFS, suited to speech).

Video source: build/video.mp4 (the silent video WITHOUT burned-in captions) when it exists, else
GeoLegalVault_Demo_v2_silent_captions.mp4 (its AI captions are burned into the picture, so a warning is printed).
Output: 1920x1080 H.264 + AAC, with captions.srt as a soft (selectable) subtitle track. Only ffmpeg is used
(imageio-ffmpeg, as in assemble.py, or ffmpeg on PATH).

Mode B places each scene's audio at that scene's start time (timeline.json). If a recording is longer than its scene
it is NEVER cut: it is reported, and the next scenes' audio is pushed later just enough not to overlap (also reported).
If the audio then runs past the end of the video, the last picture is held until your voice finishes.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SILENT_CAPTIONS = ROOT / "GeoLegalVault_Demo_v2_silent_captions.mp4"
CAPTIONLESS = ROOT / "build" / "video.mp4"
AI_VIDEOS = {(ROOT / "GeoLegalVault_Demo_v2.mp4").resolve(), SILENT_CAPTIONS.resolve()}
AUDIO_EXT = (".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg")
SR = 48000
GAP = 0.0                  # extra seconds kept between two scenes when one has to be pushed later


def find_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        exe = shutil.which("ffmpeg")
        if exe:
            return exe
    sys.exit("ffmpeg not found: install it, or run with the project venv (demo_video/.venv) that has imageio-ffmpeg")


FF = find_ffmpeg()


def run(*args):
    r = subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", *map(str, args)], capture_output=True, text=True)
    if r.returncode:
        sys.exit("ffmpeg failed:\n" + r.stderr[-1500:])


def duration(path):
    out = subprocess.run([FF, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    if not m:
        sys.exit(f"cannot read the length of {path} (is it an audio/video file?)")
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])


def clean_filters(args):
    """ffmpeg audio filters for --trim-silence / --normalize, applied to a voice file before it is placed."""
    f = []
    if args.trim_silence:
        # strip leading silence only (quiet below -45 dB for at least 0.3 s); a short 0.05 s run is kept as breathing room
        f.append("silenceremove=start_periods=1:start_duration=0.3:start_threshold=-45dB:start_silence=0.05")
    if args.normalize:
        f.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    return f


def prepare(src, dst, args, off=0.0):
    """Decode any input to 48 kHz stereo WAV with the optional clean-up, then the offset (positive = later)."""
    f = clean_filters(args)
    if off > 0:
        f.append(f"adelay={int(round(off * 1000))}|{int(round(off * 1000))}")
    elif off < 0:
        f.append(f"atrim=start={-off:.3f},asetpts=PTS-STARTPTS")
    f.append(f"aresample={SR},aformat=channel_layouts=stereo")
    run("-i", src, "-vn", "-af", ",".join(f), "-c:a", "pcm_s16le", dst)


def pick_video(args):
    if args.video:
        v = Path(args.video)
        if not v.exists():
            sys.exit(f"video not found: {v}")
        return v
    if CAPTIONLESS.exists():
        return CAPTIONLESS
    if SILENT_CAPTIONS.exists():
        print("WARNING: build/video.mp4 not found, using the silent video with the AI captions burned in; "
              "they will show next to your voice. Run assemble.py to recreate build/video.mp4, or accept this.")
        return SILENT_CAPTIONS
    sys.exit("no silent video found (build/video.mp4 or GeoLegalVault_Demo_v2_silent_captions.mp4)")


def mux(video, voice_wav, out, vlen):
    """1080p H.264 + AAC, captions.srt as a soft subtitle track. Holds the last picture if the voice outlasts the video."""
    srt = ROOT / "captions.srt"
    alen = duration(voice_wav)
    inputs = ["-i", video, "-i", voice_wav]
    if srt.exists():
        inputs += ["-i", srt]
    maps = ["-map", "0:v", "-map", "1:a"] + (["-map", "2:0"] if srt.exists() else [])
    codec_s = ["-c:s", "mov_text", "-metadata:s:s:0", "language=eng", "-metadata:s:s:0", "title=English (AI-voice wording)"] if srt.exists() else []
    vf = ["scale=1920:1080:flags=lanczos,setsar=1,format=yuv420p"]
    if alen > vlen + 0.05:
        extra = alen - vlen + 0.5
        print(f"note: your audio is {alen - vlen:.1f}s longer than the video; the last picture is held for {extra:.1f}s")
        vf.append(f"tpad=stop_mode=clone:stop_duration={extra:.3f}")
    # picture is already 1080p H.264, but re-encoding is only needed for the hold; copy otherwise
    if len(vf) == 1:
        vcodec = ["-c:v", "copy"]
        vfarg = []
    else:
        vcodec = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
        vfarg = ["-vf", ",".join(vf)]
    run(*inputs, *maps, *vfarg, *vcodec, "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), *codec_s,
        "-movflags", "+faststart", out)


def resolve_output(args):
    default = "GeoLegalVault_Demo_v2_my_voice_final.mp4" if getattr(args, "final", False) else "GeoLegalVault_Demo_v2_my_voice.mp4"
    out = Path(args.output) if args.output else ROOT / default
    out = out.resolve()
    if out in AI_VIDEOS:
        sys.exit(f"refusing to overwrite the AI-voice video {out.name}; choose another --output")
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def mode_a(args):
    audio = Path(args.audio)
    if not audio.exists():
        sys.exit(f"audio not found: {audio}")
    video = pick_video(args)
    out = resolve_output(args)
    vlen = duration(video)
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "voice.wav"
        prepare(audio, wav, args, args.offset)
        mux(video, wav, out, vlen)
        print(f"voice length {duration(wav):.1f}s, video length {vlen:.1f}s")
    print(f"WROTE {out}")


def finish_final(args, vdir, video, mix, out, placed, tmp):
    """--final: scene00 on the title slide, the scenes (cut at 19:28 of the main video), the thank-you slide."""
    import final_cut as fc
    s00 = next((vdir / f"scene00{e}" for e in AUDIO_EXT if (vdir / f"scene00{e}").exists()), None)
    if not s00:
        sys.exit(f"--final needs scene00.wav (the title slide voice) in {vdir}")
    title, thanks = Path(args.title_slide), Path(args.thanks_slide)
    for p in (title, thanks):
        if not p.exists():
            sys.exit(f"slide image not found: {p}")
    for sid, wav, at, length in placed:
        if at >= fc.CUT:
            print(f"  scene {int(sid[1:]):2d}: starts after 19:28 and is not used in the final video")
        elif at + length > fc.CUT + 0.05:
            print(f"  scene {int(sid[1:]):2d}: {at + length - fc.CUT:.1f}s of your audio falls after 19:28 and is cut (faded out over 0.5s)")
    t00 = Path(tmp) / "scene00_raw.wav"
    prepare(s00, t00, args)                          # --trim-silence / --normalize as for the scenes
    target = fc.lufs(mix, trim=fc.CUT)               # scene00 is matched to the loudness of the scenes it introduces
    t00n = Path(tmp) / "scene00_title.wav"
    gain = fc.title_audio(t00, t00n, target)
    print(f"scene00 is {fc.duration(t00n):.2f}s; loudness matched to the scenes ({target:.1f} LUFS, gain {gain:+.1f} dB)")
    srt = ROOT / "captions_final.srt"
    if not srt.exists():
        fc.shift_captions(ROOT / "captions.srt", srt, fc.duration(t00n) - fc.XFADE)
    T, start, total = fc.compose(main_video=video, main_audio=mix, title_png=title, thanks_png=thanks,
                                 title_wav=t00n, out=out, subs=srt)
    print(f"final video {total:.2f}s; main video 0:00 is at {start:.2f}s; the AI-wording captions_final.srt is the soft track")


def mode_b(args):
    if args.final:
        from voice_final import mode_b_final     # own-voice final: picture stretched to fit your voice
        return mode_b_final(args)
    tl = json.loads((ROOT / "timeline.json").read_text())
    starts, ends = tl["starts"], tl["ends"]
    vdir = Path(args.voice_dir)
    if not vdir.is_absolute():
        vdir = ROOT / vdir
    video = pick_video(args)
    out = resolve_output(args)
    vlen = duration(video)
    files = {}
    for sid in sorted(starts):
        n = int(sid[1:])
        for ext in AUDIO_EXT:
            p = vdir / f"scene{n:02d}{ext}"
            if p.exists():
                files[sid] = p
                break
    if not files:
        sys.exit(f"no scene01..scene18 audio files found in {vdir}")
    missing = [s for s in sorted(starts) if s not in files]
    if missing:
        print("no recording for scene(s): " + ", ".join(str(int(s[1:])) for s in missing) + " (those scenes stay silent)")
    placed, report, cursor = [], [], 0.0
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for sid in sorted(files):
            n = int(sid[1:])
            clean = tmp / f"{sid}_clean.wav"
            prepare(files[sid], clean, args)
            length = duration(clean)
            nominal = max(starts[sid] + args.offset, 0.0)    # --offset moves every scene by the same amount
            at = nominal if cursor - nominal < 0.05 else cursor     # ignore rounding-size overlaps
            pushed = at - nominal
            scene_secs = ends[sid] - starts[sid]
            over = length - scene_secs
            if over > 0.05:
                report.append(f"scene {n:2d}: your audio is {over:.1f}s LONGER than the scene "
                              f"({length:.1f}s of speech, scene is {scene_secs:.1f}s)")
            if pushed > 0.05:
                report.append(f"scene {n:2d}: started {pushed:.1f}s late so it does not overlap scene {n - 1}")
            placed.append((sid, clean, at, length))
            cursor = at + length + GAP
        # one input per scene, each delayed to its start, then summed (no gain change)
        inputs, filt, labels = [], [], []
        for i, (sid, wav, at, length) in enumerate(placed):
            inputs += ["-i", wav]
            ms = int(round(at * 1000))
            filt.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
            labels.append(f"[a{i}]")
        filt.append("".join(labels) + f"amix=inputs={len(placed)}:normalize=0:duration=longest[mix]")
        mix = tmp / "mix.wav"
        run(*inputs, "-filter_complex", ";".join(filt), "-map", "[mix]", "-ac", "2", "-ar", str(SR), "-c:a", "pcm_s16le", mix)
        if args.final:
            finish_final(args, vdir, video, mix, out, placed, tmp)
        else:
            mux(video, mix, out, vlen)
    print("\nScene check (nothing is cut off):")
    if report:
        print("\n".join("  " + r for r in report))
    else:
        print("  every recorded scene fits its scene time")
    print(f"WROTE {out}")


def main():
    ap = argparse.ArgumentParser(description="Replace the AI voice in the GeoLegalVault demo with your own.")
    sub = ap.add_subparsers(dest="mode", required=True)
    for name, hlp in (("a", "one continuous voice recording"), ("b", "one recording per scene")):
        p = sub.add_parser(name, help=hlp)
        if name == "a":
            p.add_argument("--audio", required=True, help="your recording (wav/mp3/m4a/...)")
        else:
            p.add_argument("--voice-dir", default="my_voice", help="folder with scene01.wav ... scene18.wav (default my_voice)")
        p.add_argument("--offset", type=float, default=0.0, help="seconds to shift your voice later (negative = earlier)")
        p.add_argument("--trim-silence", action="store_true", help="remove silence at the start of the recording(s)")
        p.add_argument("--normalize", action="store_true", help="even out loudness (about -16 LUFS)")
        if name == "b":
            p.add_argument("--final", action="store_true", help="add the title slide (scene00), cut at 19:28 and the thank-you slide")
            p.add_argument("--title-slide", default=str(ROOT / "title_slide.png"))
            p.add_argument("--thanks-slide", default=str(ROOT / "thank_you_slide.png"))
            p.add_argument("--captions", action="store_true", help="with --final: attach captions_final.srt (AI wording, not aligned to your speech)")
        p.add_argument("--video", help="silent video to use (default: build/video.mp4, else the silent_captions one)")
        p.add_argument("--output", help="output mp4 (default demo_video2/GeoLegalVault_Demo_v2_my_voice.mp4)")
    args = ap.parse_args()
    {"a": mode_a, "b": mode_b}[args.mode](args)


if __name__ == "__main__":
    main()
