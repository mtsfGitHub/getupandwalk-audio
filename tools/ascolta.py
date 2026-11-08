"""Trascrive un MP3 (o un suo pezzo) con un riconoscitore vocale, per controllare che le parole ci siano tutte.

Uso: python tools/ascolta.py file.mp3 [inizio_secondi] [fine_secondi]
"""
import subprocess
import sys

from faster_whisper import WhisperModel

f = sys.argv[1]
start = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
end = float(sys.argv[3]) if len(sys.argv) > 3 else None
cut = "pezzo.wav"
cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-i", f]
if end:
    cmd += ["-t", str(end - start)]
subprocess.run(cmd + ["-ac", "1", "-ar", "16000", cut], check=True)
model = WhisperModel("small", device="cpu", compute_type="int8")
segs, _ = model.transcribe(cut, language="it", word_timestamps=True, vad_filter=False, beam_size=5)
for s in segs:
    words = " ".join(f"{w.word.strip()}[{start + w.start:.1f}-{start + w.end:.1f}]" for w in (s.words or []))
    print(f"{start + s.start:7.1f}-{start + s.end:7.1f}  {s.text.strip()}")
    print("         ", words)
