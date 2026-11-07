"""Le voci: Kokoro (modello libero, gira sul server di GitHub) oppure toni di prova per i test."""
import numpy as np

RATE = 24000


class KokoroVoice:
    def __init__(self):
        from kokoro import KPipeline  # import here: il modello pesa e serve solo sul server
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
        if not parts:
            return np.zeros(0, dtype=np.float32)
        return _trim(np.concatenate(parts))


class TestVoice:
    """Un tono per ogni parola: serve solo a provare il montaggio senza scaricare il modello."""

    def say(self, text, voice, speed):
        words = max(1, len(text.split()))
        n = int(RATE * words * 0.38 / speed)
        t = np.arange(n) / RATE
        f = 150 if "m_" in voice else 230
        return (0.3 * np.sin(2 * np.pi * f * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 2.5 * t))).astype(np.float32)


def _trim(a, thr=0.004):
    idx = np.where(np.abs(a) > thr)[0]
    if not len(idx):
        return a
    pad = int(0.03 * RATE)
    return a[max(0, idx[0] - pad): idx[-1] + pad]


def make_voice(engine):
    return TestVoice() if engine == "prova" else KokoroVoice()
