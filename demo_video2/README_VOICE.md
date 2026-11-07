# Replace the AI voice with your own

Files: `SPEAKER_SCRIPT.md` / `SPEAKER_SCRIPT.txt` (what to say), `replace_voice.py` (puts your voice on the video).
Nothing here re-records a scene, sends a transaction or touches the app, `.env` or the databases. The AI-voice
videos are never overwritten; the result is a new file, `GeoLegalVault_Demo_v2_my_voice.mp4`.

All commands run in PowerShell from the repo root `C:\Faizal\Block chain prj\GeoLegalVault`. The script uses ffmpeg
through `imageio-ffmpeg`, which is already in the project venv:

```powershell
$py = ".\demo_video\.venv\Scripts\python.exe"
```

(If `ffmpeg` is on your PATH instead, any Python 3 works.)

## 0. Rebuild the speaker script (only if the video or narration changed)

```powershell
& $py demo_video2\make_speaker_script.py
```

It stops with a "TOO FAST" list if any sentence in `speaker_content.py` would need more than 130 words per minute.

## Mode A - one continuous recording (easier)

1. Play `demo_video2\GeoLegalVault_Demo_v2_silent_captions.mp4` and read `SPEAKER_SCRIPT.txt` on a phone or tablet.
2. Start your recorder **just before** you press play on the video, and stop it after the end card. Save as WAV, MP3 or M4A.
3. Put the file anywhere (for example `demo_video2\my_voice\full.m4a`) and run:

```powershell
& $py demo_video2\replace_voice.py a --audio demo_video2\my_voice\full.m4a --normalize --trim-silence
```

Options:

| Option | Meaning |
|---|---|
| `--offset 1.5` | your voice starts 1.5 s later on the video (use `--offset -1.5` to move it 1.5 s earlier) |
| `--trim-silence` | cut the silence at the start of your recording, **before** the offset is applied. Use it when you pressed record well before play, then fix the sync with `--offset` |
| `--normalize` | even out the loudness (about -16 LUFS) |
| `--output PATH` | write somewhere else (it refuses to overwrite the AI-voice videos) |

Tip: if you start recording and play together, do **not** use `--trim-silence` (it would shift everything earlier); use `--offset` only.

## Mode B - one file per scene

1. Record 18 files named `scene01.wav` ... `scene18.wav` (`.mp3`, `.m4a`, `.flac` also work) into `demo_video2\my_voice\`.
   Each file is one scene read start to finish. Scene times are in `SPEAKER_SCRIPT.md` (scene start - end).
2. Run:

```powershell
& $py demo_video2\replace_voice.py b --normalize --trim-silence
```

Each scene's audio is placed at that scene's start time on the video (from `timeline.json`).
A missing scene stays silent, so you can run it with only some scenes recorded.

At the end it prints a scene check. A recording is **never cut off**: if scene N is longer than its time slot, the script
says by how many seconds, and starts the following scene(s) just late enough not to overlap (it reports those too).
If your voice then runs past the end of the video, the last picture is held until you finish. To avoid pushed scenes,
trim that scene's wording or speak it a bit faster, then re-run.

`--offset N` moves every scene by the same N seconds.

Both modes print the output path (`WROTE ...`). The result is 1920x1080 H.264 + AAC, with `captions.srt` as a soft,
selectable subtitle track (the captions are the AI-voice wording, so switch them off or edit `captions.srt` if your
wording differs a lot).

Which picture: the script uses `demo_video2\build\video.mp4` (silent video **without** burned-in captions) when it exists.
Otherwise it falls back to `GeoLegalVault_Demo_v2_silent_captions.mp4` and warns you that the AI captions are burned in.

## Final version with your own voice, title slide and thank-you slide (Mode B)

```powershell
& $py demo_video2\replace_voice.py b --final --normalize --trim-silence
```

Needs `my_voice\scene00.wav` (title slide) and `scene01.wav` ... `scene18.wav`, plus `title_slide.png` and `thank_you_slide.png`
in `demo_video2\`. Output: `GeoLegalVault_Demo_v2_my_voice_final.mp4` and `...my_voice_final.report.json` (per-scene numbers).
Your voice is never cut or moved off its scene; the **picture** is adjusted:

- each scene's audio starts at the scene's first frame; the silence before your first word is trimmed to 0.15 s (`--trim-silence`)
  and the silence after your last word to 0.35 s;
- if your audio is longer than the scene, the last frame is held for the overrun so later scenes stay in sync; if shorter, the
  picture is unchanged;
- all scenes get the same loudness (-20.6 LUFS, like the AI narration), no denoising;
- the main part ends 0.5 s after your last word in scene 18 (not at a fixed time), then the 3 s thank-you slide;
- no subtitle track (add `--captions` to attach `captions_final.srt`, which has the AI wording and will not match your speech);
- the printed table lists picture length, audio length, overrun, gain, noise floor and flags (voice running to the very end of a
  file, hiss) per scene.

The AI-voice finals are built by `make_final.py` (`GeoLegalVault_Demo_v2_final.mp4`, `..._final_silent_captions.mp4`, `captions_final.srt`).

## Recording tips

**Windows tools**
- *Voice Recorder* (Start menu): fine for Mode A or Mode B; files are M4A, which the script reads. Press the red button, speak, stop; recordings are listed on the left (right-click > Open file location).
- *Audacity* (free): more control. Project rate 48000 Hz, mono is fine. Record, then File > Export > WAV. Use Effect > Noise Reduction only if you hear steady hiss.

**Room and microphone**
- Quiet room, door shut, phone on silent, fan/AC off. Soft surfaces (curtains, sofa) beat an empty hard room.
- Headset or phone-headphone mic about a hand-width (10-15 cm) from your mouth, slightly to the side so breaths don't pop. Do a 10-second test, listen on headphones, fix the level so the loudest word is not clipping.
- Drink water, keep the script on a second screen or phone, and read at the pace in the script: no sentence needs more than 130 words per minute, and `[PAUSE]` marks places where the video holds.

**Whole video or one scene at a time?**
- Whole video (Mode A): one take, natural flow, but a mistake means redoing from there, and the video can't be paused for you.
- One scene at a time (Mode B): easier to get right, 30-130 seconds each. Recommended for a first pass.
- Pause the video at each scene start (the times are in the script), press record, play, read, stop. Name the file `sceneNN.wav` right away.

**Re-doing one scene**
- Mode B: re-record only that file (same name, it replaces the old one) and run the command again; it takes a few minutes because the video is processed once.
- Mode A: cannot re-do one scene; either record the whole thing again or switch to Mode B for the bad scene.

**Checking sync**
1. Open `GeoLegalVault_Demo_v2_my_voice.mp4` and jump to a scene start from `SPEAKER_SCRIPT.md` (for example 5:36, the geofence limit). Your sentence should begin as the screen changes.
2. Check three places: near the start (0:45), the middle (10:34, MISMATCH appears) and the end (19:29).
3. If the voice is steadily late or early by the same amount, re-run with `--offset` (positive = later, negative = earlier). If it drifts, you most likely paused the video while recording (Mode A); use Mode B.
4. Say the three honest limits (tamper-evident, geofence is policy, audit log has no hash chain yet); they are marked **MUST SAY** in the script.
