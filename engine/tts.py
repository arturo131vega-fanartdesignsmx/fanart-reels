"""Voice-over with Kokoro (offline TTS) + subtitle timings per chunk.

script: list of sentences
  {"chunks": ["Okay, be honest...", ["with code twenty-five off.", "with code 25OFF"], ...],
   "speed": 1.0, "pause": 0.3}
A chunk is either a string (spoken == displayed) or [spoken, displayed].
"""
import json
import numpy as np


def _trim(s, sr):
    idx = np.where(np.abs(s) > 0.01)[0]
    if len(idx) == 0:
        return s
    return s[max(0, idx[0] - int(0.03 * sr)): idx[-1] + int(0.07 * sr)]


def synth(script, voice, base_speed, model_dir, lead=0.2, tail=0.7):
    from kokoro_onnx import Kokoro
    k = Kokoro(f"{model_dir}/kokoro-v1.0.onnx", f"{model_dir}/voices-v1.0.bin")
    if "+" in voice:
        a, b = voice.split("+")
        style = 0.6 * k.get_voice_style(a) + 0.4 * k.get_voice_style(b)
    else:
        style = voice

    def syn(text, sp):
        s, sr = k.create(text, voice=style, speed=sp, lang="en-us")
        return _trim(s.astype(np.float32), sr), sr

    sr = 24000
    audio = [np.zeros(int(lead * sr), np.float32)]
    t = lead
    subs = []
    for sent in script:
        chunks = [(c, c) if isinstance(c, str) else (c[0], c[1]) for c in sent["chunks"]]
        sp = base_speed * float(sent.get("speed", 1.0))
        text = " ".join(c[0] for c in chunks)
        s, sr = syn(text, sp)
        d = len(s) / sr
        if len(chunks) > 1:
            cl = np.array([len(syn(c[0], sp)[0]) for c in chunks], float)
            cum = np.cumsum(cl / cl.sum())[:-1] * d
            hop = int(0.01 * sr)
            env = np.sqrt(np.convolve(s ** 2, np.ones(hop * 3) / (hop * 3), "same"))[::hop]
            thr = max(env.max() * 0.04, 1e-4)
            bounds = []
            for b in cum:
                lo, hi = max(int((b - 0.25) * 100), 1), min(int((b + 0.25) * 100), len(env) - 1)
                j = lo + int(np.argmin(env[lo:hi] + np.abs(np.arange(lo, hi) / 100 - b) * 0.02))
                while j < len(env) - 1 and env[j] < thr and (j / 100 - b) < 0.4:
                    j += 1
                bounds.append(max(j / 100 - 0.06, 0))
            edges = [0] + bounds + [d]
        else:
            edges = [0, d]
        for (spk, disp), a0, a1 in zip(chunks, edges[:-1], edges[1:]):
            subs.append({"t0": round(t + a0, 3), "t1": round(t + a1, 3), "text": disp})
        audio.append(s)
        t += d
        pz = float(sent.get("pause", 0.3))
        if pz:
            audio.append(np.zeros(int(pz * sr), np.float32))
            t += pz
    audio.append(np.zeros(int(tail * sr), np.float32))
    t += tail
    y = np.concatenate(audio)
    return y, sr, {"dur": round(len(y) / sr, 3), "subs": subs}


if __name__ == "__main__":
    import sys
    import soundfile as sf
    spec = json.load(open(sys.argv[1]))
    y, sr, meta = synth(spec["script"], spec.get("voice", "af_heart"), spec.get("speed", 1.04), sys.argv[2])
    sf.write(sys.argv[3], y, sr)
    json.dump(meta, open(sys.argv[3].rsplit(".", 1)[0] + ".json", "w"), indent=1)
    print(meta["dur"])
