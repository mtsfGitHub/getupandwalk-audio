"""Le voci. Nel modello si scrivono così:
    im_nicola  oppure  kokoro:im_nicola     → Kokoro (anche voci di altre lingue, lette con la pronuncia italiana)
    piper:it_IT-paola-medium                → Piper (voci addestrate su registrazioni italiane)
    edge:it-IT-ElsaNeural                   → le voci di Microsoft Edge (servizio non ufficiale: se non risponde
                                              si usa la voce di riserva e si apre un avviso)
    prova                                   → toni al posto delle parole, per provare il montaggio
"""
import numpy as np

RATE = 24000


class KokoroEngine:
    def __init__(self):
        from kokoro import KPipeline  # pesante: si carica solo se serve
        self.pipe = KPipeline(lang_code="i", repo_id="hexgrad/Kokoro-82M")

    def say(self, text, voice, speed):
        parts = []
        for res in self.pipe(text, voice=voice, speed=speed, split_pattern=None):
            audio = getattr(res, "audio", None)
            if audio is None:
                audio = res[2]
            if audio is None:
                continue
            a = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio)
            parts.append(a.astype(np.float32).reshape(-1))
        return np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)


class PiperEngine:
    def __init__(self):
        self.voices = {}

    def _load(self, name):
        if name not in self.voices:
            from huggingface_hub import hf_hub_download
            from piper import PiperVoice
            lang_region, speaker, quality = name.split("-")
            folder = f"{lang_region.split('_')[0]}/{lang_region}/{speaker}/{quality}"
            model = hf_hub_download("rhasspy/piper-voices", f"{folder}/{name}.onnx")
            hf_hub_download("rhasspy/piper-voices", f"{folder}/{name}.onnx.json")
            self.voices[name] = PiperVoice.load(model)
        return self.voices[name]

    def say(self, text, voice, speed):
        from piper import SynthesisConfig
        from scipy.signal import resample_poly
        v = self._load(voice)
        chunks, rate = [], RATE
        for ch in v.synthesize(text, syn_config=SynthesisConfig(length_scale=1.0 / speed)):
            chunks.append(ch.audio_float_array.astype(np.float32))
            rate = ch.sample_rate
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        a = np.concatenate(chunks)
        if rate != RATE:
            from math import gcd
            g = gcd(RATE, rate)
            a = resample_poly(a, RATE // g, rate // g).astype(np.float32)
        return a * 0.8


def _italian_ssml(tc, escaped_text):
    """Come quella di edge-tts, ma dichiara l'italiano: le voci "multilingue" (es. Giuseppe) altrimenti
    leggono in inglese le frasi corte o fatte di soli nomi."""
    if isinstance(escaped_text, bytes):
        escaped_text = escaped_text.decode("utf-8")
    return ("<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='it-IT'>"
            f"<voice name='{tc.voice}'>"
            f"<prosody pitch='{tc.pitch}' rate='{tc.rate}' volume='{tc.volume}'>{escaped_text}</prosody>"
            "</voice></speak>")


CARRIER = "Ecco una breve frase, detta in lingua italiana:"


def _norm(w):
    import re
    return re.sub(r"[^\w]", "", w.lower())


def _phrase_start(words, text):
    """Secondi in cui inizia la frase vera, dopo la frase di appoggio (dai tempi delle parole di Edge)."""
    carrier = [_norm(w) for w in CARRIER.split() if _norm(w)]
    first = next((_norm(w) for w in text.split() if _norm(w)), "")
    seen = 0
    for offset, w in words:
        nw = _norm(w)
        if not nw:
            continue
        if seen >= len(carrier) and nw == first:
            return offset / 1e7
        if seen < len(carrier) and nw == carrier[seen]:
            seen += 1
        elif seen >= len(carrier) - 1 and nw == first:
            return offset / 1e7
    return None


class EdgeEngine:
    def __init__(self):
        self.available = None
        self.resolved = {}
        self.force_italian = True
        self._orig_ssml = None

    def _resolve(self, voice):
        """Accetta anche nomi approssimativi (it-IT-GiuseppeNeural → la voce di Giuseppe che esiste davvero)."""
        if voice not in self.resolved:
            import asyncio

            import edge_tts
            if self.available is None:
                self.available = [v["ShortName"] for v in asyncio.run(edge_tts.list_voices())]
            if voice in self.available:
                self.resolved[voice] = voice
            else:
                person = voice.split("-")[-1].replace("MultilingualNeural", "").replace("Neural", "").lower()
                lang = "-".join(voice.split("-")[:2]) if voice.count("-") >= 2 else "it-IT"
                cands = sorted((v for v in self.available if v.startswith(lang + "-") and person in v.lower()), key=len)
                if not cands:
                    raise RuntimeError(f"la voce {voice} non esiste tra le voci di Edge")
                self.resolved[voice] = cands[0]
                print(f"Voce {voice} → {cands[0]}")
        return self.resolved[voice]

    def say(self, text, voice, speed):
        import asyncio
        import subprocess
        import time

        import edge_tts
        import edge_tts.communicate as ec
        if self._orig_ssml is None:
            self._orig_ssml = ec.mkssml
        voice = self._resolve(voice)
        rate = f"{round((speed - 1) * 100):+d}%"
        last, plain = None, False
        for attempt in range(4):
            use_it = self.force_italian and "Multilingual" in voice
            ec.mkssml = _italian_ssml if use_it else self._orig_ssml
            # Le voci "multilingue" (Giuseppe) sulle frasi brevi scelgono l'inglese: la frase viene detta
            # dentro una frase italiana più lunga e poi si tiene solo il pezzo giusto.
            short = not plain and "Multilingual" in voice and len(text.split()) <= 10
            send = f"{CARRIER} {text}" if short else text
            try:
                buf, words = bytearray(), []

                async def run():
                    com = edge_tts.Communicate(send, voice, rate=rate,
                                               boundary="WordBoundary" if short else "SentenceBoundary")
                    async for ch in com.stream():
                        if ch["type"] == "audio":
                            buf.extend(ch["data"])
                        elif ch["type"] == "WordBoundary":
                            words.append((ch["offset"], ch["text"]))

                asyncio.run(run())
                if not buf:
                    raise RuntimeError("nessun audio ricevuto")
                raw = subprocess.run(["ffmpeg", "-v", "error", "-i", "-", "-ac", "1", "-ar", str(RATE), "-f", "f32le", "-"],
                                     input=bytes(buf), check=True, capture_output=True).stdout
                a = np.frombuffer(raw, dtype=np.float32).copy()
                if short:
                    start = _phrase_start(words, text)
                    if start is None:
                        print(f"Non trovo dove inizia «{text}»: la leggo da sola.")
                        plain = True
                        continue
                    a = a[max(0, int((start - 0.03) * RATE)):]
                return a
            except Exception as e:  # rete, servizio cambiato, voce sparita…
                last = e
                if use_it:  # il servizio non accetta la lingua dichiarata: si torna al modo normale
                    print(f"Lingua italiana forzata non accettata ({e}); continuo senza.")
                    self.force_italian = False
                time.sleep(3 * (attempt + 1))
        raise RuntimeError(f"le voci di Edge non rispondono ({last})")


class TestEngine:
    def say(self, text, voice, speed):
        words = max(1, len(text.split()))
        n = int(RATE * words * 0.38 / speed)
        t = np.arange(n) / RATE
        f = 150 if "m_" in voice else 230
        return (0.3 * np.sin(2 * np.pi * f * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 2.5 * t))).astype(np.float32)


class Voices:
    def say_both(self, text, v1, v2, speed):
        """Le due voci insieme, come in coro: la più veloce si adatta alla più lenta."""
        a, b = self.say(text, v1, speed), self.say(text, v2, speed)
        n = max(len(a), len(b))
        return (_stretch(a, n) + _stretch(b, n)) * 0.62

    def __init__(self, test=False, fallback="im_nicola"):
        self.test = test
        self.engines = {}
        self.fallback = fallback
        self.broken = {}      # motore → errore, se ha smesso di funzionare in questa esecuzione

    def _engine(self, kind):
        if self.test:
            kind = "prova"
        if kind not in self.engines:
            self.engines[kind] = {"kokoro": KokoroEngine, "piper": PiperEngine, "edge": EdgeEngine,
                                  "prova": TestEngine}[kind]()
        return self.engines[kind]

    def say(self, text, voice, speed):
        kind, _, name = voice.partition(":") if ":" in voice else ("kokoro", "", voice)
        if kind in self.broken:
            return self.say(text, self.fallback, speed)
        try:
            return _trim(self._engine(kind).say(text, name, speed))
        except Exception as e:
            if voice == self.fallback:
                raise
            print(f"ATTENZIONE: {e}. Uso la voce di riserva ({self.fallback}).")
            self.broken[kind] = str(e)
            return self.say(text, self.fallback, speed)


def _stretch(a, length):
    """Allunga o accorcia un pezzo di voce senza cambiarne il tono (ffmpeg atempo)."""
    import subprocess
    if len(a) == 0 or abs(len(a) - length) < RATE * 0.03:
        return np.pad(a, (0, max(0, length - len(a))))[:length]
    factor = min(2.0, max(0.5, len(a) / length))
    raw = subprocess.run(["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(RATE), "-ac", "1", "-i", "-",
                          "-filter:a", f"atempo={factor:.4f}", "-f", "f32le", "-"],
                         input=a.astype(np.float32).tobytes(), check=True, capture_output=True).stdout
    b = np.frombuffer(raw, dtype=np.float32)
    return np.pad(b, (0, max(0, length - len(b))))[:length]


def _trim(a, thr=0.004):
    idx = np.where(np.abs(a) > thr)[0]
    if not len(idx):
        return a
    pad = int(0.03 * RATE)
    return a[max(0, idx[0] - pad): idx[-1] + pad]


def make_voice(engine, fallback="im_nicola"):
    return Voices(test=(engine == "prova"), fallback=fallback)
