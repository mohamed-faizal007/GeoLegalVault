"""Extract frames from the final video at given times: python qa/frames.py video.mp4 out_prefix t1 t2 ..."""
import subprocess, sys, imageio_ffmpeg
ff = imageio_ffmpeg.get_ffmpeg_exe()
vid, prefix, *times = sys.argv[1:]
for t in times:
    out = f"{prefix}_{float(t):07.2f}.png"
    subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-ss", t, "-i", vid, "-frames:v", "1", "-vf", "scale=1280:-1", out], check=True)
    print(out)
