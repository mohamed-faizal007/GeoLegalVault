"""Contact sheet: python qa/sheet.py out.png cols t1 t2 ...  (frames of the final video at those times, 640x360 each)"""
import subprocess, sys, imageio_ffmpeg
ff = imageio_ffmpeg.get_ffmpeg_exe()
out, cols, *ts = sys.argv[1:]
cols = int(cols)
files = []
for i, t in enumerate(ts):
    f = f"qa/_sh{i}.png"
    subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-ss", t, "-i", "GeoLegalVault_Demo_v2.mp4", "-frames:v", "1", "-vf", "scale=%s:-1" % __import__("os").environ.get("W","640") + "", f], check=True)
    files.append(f)
while len(files) % cols:
    files.append(files[-1])
rows = []
for r in range(0, len(files), cols):
    row = f"qa/_row{r}.png"
    inp = sum([["-i", f] for f in files[r:r + cols]], [])
    subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", *inp, "-filter_complex", f"hstack=inputs={cols}", row], check=True)
    rows.append(row)
inp = sum([["-i", f] for f in rows], [])
subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", *inp, "-filter_complex", f"vstack=inputs={len(rows)}", out], check=True)
