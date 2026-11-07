"""Build the two final AI-voice videos (title slide + main video cut at 19:28 + thank-you slide) and captions_final.srt.

    python demo_video2/make_final.py

Writes NEW files only: GeoLegalVault_Demo_v2_final.mp4, GeoLegalVault_Demo_v2_final_silent_captions.mp4,
captions_final.srt. The existing videos are only read. Inputs: title_slide.png, thank_you_slide.png, my_voice/scene00.wav.
"""
import sys
import tempfile
from pathlib import Path

import final_cut as fc

ROOT = fc.ROOT
MAIN = ROOT / "GeoLegalVault_Demo_v2.mp4"                    # picture without burned captions + AI voice + soft subs
MAIN_CAPS = ROOT / "GeoLegalVault_Demo_v2_silent_captions.mp4"   # picture with burned-in captions, no audio
OUT = ROOT / "GeoLegalVault_Demo_v2_final.mp4"
OUT_SILENT = ROOT / "GeoLegalVault_Demo_v2_final_silent_captions.mp4"
SRT = ROOT / "captions_final.srt"


def main():
    title, thanks = ROOT / "title_slide.png", ROOT / "thank_you_slide.png"
    s00 = ROOT / "my_voice" / "scene00.wav"
    for p in (title, thanks, s00, MAIN, MAIN_CAPS, ROOT / "captions.srt"):
        if not p.exists():
            sys.exit(f"missing input: {p}")
    T = fc.duration(s00)
    print(f"scene00.wav is {T:.2f}s (the plan said 24.0s); the title clip is exactly that long")
    shift = T - fc.XFADE
    n = fc.shift_captions(ROOT / "captions.srt", SRT, shift)
    print(f"captions_final.srt: {n} captions, shifted by +{shift:.2f}s, last one ends at {fc.CUT + shift:.2f}s")
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "title.wav"
        target = fc.lufs(MAIN, trim=fc.CUT)
        gain = fc.title_audio(s00, wav, target)
        print(f"narration loudness {target:.1f} LUFS; scene00 gain {gain:+.1f} dB to match")
        _, start, total = fc.compose(main_video=MAIN, main_audio=MAIN, title_png=title, thanks_png=thanks,
                                     title_wav=wav, out=OUT, subs=SRT)
        print(f"WROTE {OUT}  ({total:.2f}s)")
        fc.compose(main_video=MAIN_CAPS, main_audio=None, title_png=title, thanks_png=thanks,
                   title_wav=wav, out=OUT_SILENT)
        print(f"WROTE {OUT_SILENT}  ({total:.2f}s)")
    print(f"main video 0:00 sits at {start:.2f}s on the final timeline; main time t = final time - {start:.2f}s")


if __name__ == "__main__":
    main()
