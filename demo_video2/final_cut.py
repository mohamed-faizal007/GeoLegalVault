"""Title slide + cut main video + thank-you slide, shared by make_final.py (AI voice) and replace_voice.py --final.

Timeline of a final video (T = exact length of scene00.wav):
    0 .. T            title slide (still image), 0.5 s fade-in from black, scene00 voice
    T-0.5 ..          main video from 0:00 to CUT (19:28), cross-faded 0.5 s into the title slide; main time t is at t + (T-0.5)
    + THANKS_SECS     thank-you slide, silent, 0.5 s fade-out to black at the end
The main audio is faded out over the last 0.5 s before CUT (it never ends in a hard cut). Only ffmpeg is used; nothing is
recorded or sent. Intermediate files go to a temporary folder, outputs are always new files.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CUT = 19 * 60 + 28.0          # seconds of the main video that are kept (19:28)
XFADE = 0.5
THANKS_SECS = 3.0
SR = 48000


def find_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        import shutil
        exe = shutil.which("ffmpeg")
        if exe:
            return exe
    sys.exit("ffmpeg not found")


FF = find_ffmpeg()


def run(*args, quiet=True):
    r = subprocess.run([FF, "-hide_banner", "-loglevel", "error" if quiet else "info", "-y", *map(str, args)],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit("ffmpeg failed:\n" + r.stderr[-1800:])


def duration(path):
    out = subprocess.run([FF, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    if not m:
        sys.exit(f"cannot read the length of {path}")
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])


def lufs(path, trim=None):
    """Integrated loudness (EBU R128) of a file's audio, optionally of its first `trim` seconds."""
    pre = ["-t", f"{trim}"] if trim else []
    err = subprocess.run([FF, "-hide_banner", *pre, "-i", str(path), "-vn", "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", err.split("Summary:")[-1])
    if not m:
        sys.exit(f"could not measure the loudness of {path}")
    return float(m[0])


def title_audio(scene00, dst, target_lufs):
    """scene00 -> 48 kHz stereo WAV, exactly its own length, gain set so its loudness equals `target_lufs`."""
    # measure after the mono -> stereo copy: two identical channels read 3 LU louder than the one mono channel
    flat = Path(dst).with_suffix(".stereo.wav")
    run("-i", scene00, "-vn", "-af", f"aresample={SR},pan=stereo|c0=c0|c1=c0", "-c:a", "pcm_s16le", flat)
    gain = target_lufs - lufs(flat)
    run("-i", flat, "-af", f"volume={gain:.2f}dB,alimiter=limit=0.89:level=disabled,aformat=channel_layouts=stereo",
        "-c:a", "pcm_s16le", dst)
    flat.unlink()
    return gain


def _ts(x):
    h, r = divmod(x, 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")


def _sec(t):
    h, m, s = t.replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def shift_captions(src, dst, shift, cut=CUT):
    """captions.srt shifted by `shift` seconds; captions after `cut` are dropped, the one running over it is clipped."""
    out, n = [], 0
    for blk in Path(src).read_text(encoding="utf-8").strip().split("\n\n"):
        ln = blk.split("\n")
        a, z = (_sec(x) for x in ln[1].split(" --> "))
        if a >= cut - 0.05:
            continue
        z = min(z, cut)
        n += 1
        out.append(f"{n}\n{_ts(a + shift)} --> {_ts(z + shift)}\n" + "\n".join(ln[2:]) + "\n")
    Path(dst).write_text("\n".join(out), encoding="utf-8")
    return n


def compose(*, main_video, main_audio, title_png, thanks_png, title_wav, out, subs=None, cut=CUT):
    """Write `out`. main_audio None = silent main part. title_wav is already processed (48k stereo).
    subs: soft subtitle .srt added as a selectable track (None = no track)."""
    T = duration(title_wav)
    start = T - XFADE                       # where main time 0 sits on the final timeline
    total = start + cut + THANKS_SECS
    vf = (
        f"[0:v]fps=30,scale=1920:1080:flags=lanczos,setsar=1,format=yuv420p,fade=t=in:st=0:d=0.5[t];"
        f"[2:v]trim=0:{cut:.3f},setpts=PTS-STARTPTS,fps=30,scale=1920:1080:flags=lanczos,setsar=1,format=yuv420p[m];"
        f"[t][m]xfade=transition=fade:duration={XFADE}:offset={start:.3f}[tm];"
        f"[1:v]fps=30,scale=1920:1080:flags=lanczos,setsar=1,format=yuv420p,trim=0:{THANKS_SECS},setpts=PTS-STARTPTS,"
        f"fade=t=out:st={THANKS_SECS - 0.5}:d=0.5[y];"
        f"[tm][y]concat=n=2:v=1:a=0[v]"
    )
    ms = int(round(start * 1000))
    af = f"[3:a]atrim=0:{T:.3f},asetpts=PTS-STARTPTS[ta];"
    if main_audio:
        af += (f"[4:a]atrim=0:{cut:.3f},asetpts=PTS-STARTPTS,aresample={SR},aformat=channel_layouts=stereo,"
               f"afade=t=out:st={cut - 0.5:.3f}:d=0.5,adelay={ms}|{ms}[ma];[ta][ma]amix=inputs=2:normalize=0:duration=longest[mx];")
    else:
        af += "[ta]anull[mx];"
    af += f"[mx]apad=whole_dur={total:.3f},atrim=0:{total:.3f}[a]"
    cmd = ["-loop", "1", "-framerate", "30", "-t", f"{T:.3f}", "-i", title_png,
           "-loop", "1", "-framerate", "30", "-t", f"{THANKS_SECS}", "-i", thanks_png,
           "-i", main_video, "-i", title_wav]
    if main_audio:
        cmd += ["-i", main_audio]
    smap = []
    if subs:
        cmd += ["-i", subs]
        smap = ["-map", f"{5 if main_audio else 4}:0", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng"]
    run(*cmd, "-filter_complex", vf + ";" + af, "-map", "[v]", "-map", "[a]", *smap,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "160k", "-ar", str(SR), "-ac", "2", "-movflags", "+faststart", "-t", f"{total:.3f}", out)
    return T, start, total


def analyze(src, tmp):
    """Level facts about a voice file, from 50 ms frames of a 16 kHz mono copy (pure Python, no numpy):
    noise floor (10th percentile, dBFS), speech level (90th percentile), time of the first/last voiced frame, gaps > 2 s."""
    import array
    import math
    import wave
    mono = Path(tmp) / (Path(src).stem + "_an.wav")
    run("-i", src, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", mono)
    w = wave.open(str(mono))
    a = array.array("h")
    a.frombytes(w.readframes(w.getnframes()))
    hop = 800
    rms = []
    for i in range(0, len(a) - hop, hop):
        c = a[i:i + hop:2]
        rms.append(10 * math.log10(sum(x * x for x in c) / len(c) / 32768 ** 2 + 1e-12))
    s = sorted(rms)
    floor, speech = s[int(len(s) * 0.10)], s[int(len(s) * 0.90)]
    thr = max(floor + 8, speech - 25)
    voiced = [i for i, v in enumerate(rms) if v > thr]
    gaps, prev = [], None
    for i in voiced:
        if prev is not None and (i - prev) * 0.05 > 2.0:
            gaps.append((round(prev * 0.05 + 0.05, 1), round((i - prev) * 0.05 - 0.05, 1)))
        prev = i
    return {"dur": len(a) / 16000, "floor": floor, "speech": speech,
            "first": voiced[0] * 0.05 if voiced else 0.0, "last": (voiced[-1] + 1) * 0.05 if voiced else len(a) / 16000,
            "gaps": gaps}
