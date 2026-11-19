import json, numpy as np, soundfile as sf, sys
from kokoro_onnx import Kokoro
k = Kokoro('kokoro-v1.0.onnx', 'voices-v1.0.bin')
voice, out = sys.argv[1], sys.argv[2]; base = float(sys.argv[3])
# (spoken sentence, speed factor, pause after, [(spoken chunk, subtitle)])
S = [
 ("Okay, be honest... would you add this one to your binder?", 0.97, 0.30,
   [("Okay, be honest...", "Okay, be honest..."), ("would you add this one", "would you add this one"), ("to your binder?", "to your binder?")]),
 ("Every card's handmade, it's holographic, and it's real trading card size.", 1.03, 0.26,
   [("Every card's handmade,", "Every card's handmade,"), ("it's holographic,", "it's holographic,"), ("and it's real trading card size.", "and it's real trading card size.")]),
 ("Oh, and if you grab two or more, you save twenty-five percent with code twenty-five off.", 1.05, 0.30,
   [("Oh, and if you grab", "Oh, and if you grab"), ("two or more,", "two or more,"), ("you save twenty-five percent", "you save 25%"), ("with code twenty-five off.", "with code 25OFF")]),
 ("Link's in my bio!", 1.0, 0.0, [("Link's in my bio!", "Link's in my bio!")]),
]
if '+' in voice:
    a, b = voice.split('+'); st = 0.6 * k.get_voice_style(a) + 0.4 * k.get_voice_style(b)
else:
    st = voice
def syn(text, sp):
    s, sr = k.create(text, voice=st, speed=sp, lang='en-us'); s = s.astype(np.float32)
    idx = np.where(np.abs(s) > 0.01)[0]
    return s[max(0, idx[0] - int(0.03 * sr)): idx[-1] + int(0.07 * sr)], sr
sr = 24000; audio = [np.zeros(int(0.2 * sr), np.float32)]; t = 0.2; subs = []
for text, f, pz, chunks in S:
    sp = base * f
    s, sr = syn(text, sp); d = len(s) / sr
    # chunk proportions from separately synthesized chunk lengths, snapped to quiet spots
    cl = np.array([len(syn(c[0], sp)[0]) for c in chunks], float); cum = np.cumsum(cl / cl.sum())[:-1] * d
    hop = int(0.01 * sr); env = np.sqrt(np.convolve(s ** 2, np.ones(hop * 3) / (hop * 3), 'same'))[::hop]
    bounds = []
    for b in cum:
        lo, hi = int((b - 0.25) * 100), int((b + 0.25) * 100)
        lo, hi = max(lo, 1), min(hi, len(env) - 1)
        j = lo + int(np.argmin(env[lo:hi] + np.abs(np.arange(lo, hi) / 100 - b) * 0.02))
        thr = max(env.max() * 0.04, 1e-4)
        while j < len(env) - 1 and env[j] < thr and (j / 100 - b) < 0.4: j += 1   # move to next onset
        bounds.append(max(j / 100 - 0.06, 0))
    edges = [0] + bounds + [d]
    for (spk, disp), a0, a1 in zip(chunks, edges[:-1], edges[1:]):
        subs.append({'t0': round(t + a0, 3), 't1': round(t + a1, 3), 'text': disp})
    audio.append(s); t += d
    if pz: audio.append(np.zeros(int(pz * sr), np.float32)); t += pz
audio.append(np.zeros(int(0.7 * sr), np.float32)); t += 0.7
y = np.concatenate(audio); sf.write(out, y, sr)
json.dump({'dur': round(len(y) / sr, 3), 'subs': subs}, open(out.replace('.wav', '.json'), 'w'), indent=1)
print(out, round(len(y) / sr, 2))
