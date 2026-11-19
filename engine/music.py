"""Original procedural chiptune background music (8-bit style), generated from a seed.

Everything is synthesised here (square/triangle/noise oscillators), so the result is
original audio with no third-party rights. Used quietly under the voice-over.
"""
import numpy as np

SR = 48000
PROGRESSIONS = [  # scale degrees (0-based) of chord roots
    [0, 4, 5, 3],   # I V vi IV
    [5, 3, 0, 4],   # vi IV I V
    [0, 5, 3, 4],   # I vi IV V
    [0, 3, 4, 3],   # I IV V IV
    [3, 4, 2, 5],   # IV V iii vi
]
MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]


def _freq(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def _square(f, n, duty=0.5, phase=0.0):
    t = (np.arange(n) / SR * f + phase) % 1.0
    return np.where(t < duty, 1.0, -1.0)


def _triangle(f, n):
    t = (np.arange(n) / SR * f) % 1.0
    return 4 * np.abs(t - 0.5) - 1


def _env(n, a=0.005, d=0.08, s=0.55, r=0.04):
    e = np.ones(n) * s
    na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
    na = max(1, min(na, n)); e[:na] = np.linspace(0, 1, na)
    if na + nd < n:
        e[na:na + nd] = np.linspace(1, s, nd)
    if nr < n:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def _lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):  # small arrays per note; fine
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def _lp_fast(x, cutoff):
    # vectorised one-pole via scipy-free cumulative filter (block approximation)
    from scipy.signal import lfilter
    a = np.exp(-2 * np.pi * cutoff / SR)
    return lfilter([1 - a], [1, -a], x)


def chiptune(duration, seed=0):
    rng = np.random.default_rng(seed)
    bpm = int(rng.integers(104, 129))
    beat = 60 / bpm
    root = int(rng.integers(55, 63))          # G3..D#4
    scale = MAJOR if rng.random() < 0.75 else MINOR
    prog = PROGRESSIONS[int(rng.integers(len(PROGRESSIONS)))]
    duty_lead = float(rng.choice([0.125, 0.25, 0.5]))
    arp_pattern = [[0, 2, 4, 2], [0, 4, 2, 4], [0, 2, 4, 7], [4, 2, 0, 2]][int(rng.integers(4))]
    n = int(duration * SR) + SR
    out = np.zeros(n)

    def deg(d, octave=0):
        o, i = divmod(d, 7)
        return root + scale[i] + 12 * (o + octave)

    bar = 4 * beat
    nbars = int(np.ceil(duration / bar)) + 1
    # melody motif: 8 eighth-notes per bar, reused with variation
    motif = [int(x) for x in rng.choice([0, 1, 2, 3, 4, 5, 7, -1], size=8, p=[.2, .1, .2, .1, .2, .05, .05, .1])]
    for b in range(nbars):
        chord = prog[b % len(prog)]
        t0 = b * bar
        # bass: triangle on root, quarter notes with octave bounce
        for q in range(4):
            s = int((t0 + q * beat) * SR); ln = int(beat * 0.9 * SR)
            if s + ln >= n: break
            f = _freq(deg(chord, -2 if q % 2 == 0 else -1))
            out[s:s + ln] += 0.32 * _triangle(f, ln) * _env(ln, d=0.1, s=0.7)
        # arpeggio: 16th notes, soft square
        for k in range(16):
            s = int((t0 + k * beat / 4) * SR); ln = int(beat / 4 * 0.85 * SR)
            if s + ln >= n: break
            d = chord + arp_pattern[k % 4]
            f = _freq(deg(d, 0))
            out[s:s + ln] += 0.10 * _square(f, ln, 0.25) * _env(ln, d=0.05, s=0.4)
        # lead melody (from bar 2), eighth notes, varies every other bar
        if b >= 1:
            for k in range(8):
                step = motif[k] if b % 2 else motif[(k + 3) % 8]
                if step < 0: continue
                s = int((t0 + k * beat / 2) * SR); ln = int(beat / 2 * 0.8 * SR)
                if s + ln >= n: break
                f = _freq(deg(chord + step, 1))
                vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * np.arange(ln) / SR)
                ph = np.cumsum(f * vib / SR) % 1.0
                wave = np.where(ph < duty_lead, 1.0, -1.0)
                out[s:s + ln] += 0.11 * wave * _env(ln, d=0.12, s=0.5)
        # drums: kick on 1 and 3, snare 2 and 4, hats 8ths
        for q in range(4):
            s = int((t0 + q * beat) * SR)
            if q in (0, 2):
                ln = int(0.18 * SR)
                if s + ln < n:
                    tt = np.arange(ln) / SR
                    f = 120 * np.exp(-tt * 18) + 45
                    out[s:s + ln] += 0.45 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 14)
            else:
                ln = int(0.12 * SR)
                if s + ln < n:
                    out[s:s + ln] += 0.16 * rng.uniform(-1, 1, ln) * np.exp(-np.arange(ln) / SR * 28)
        for e8 in range(8):
            s = int((t0 + e8 * beat / 2) * SR); ln = int(0.03 * SR)
            if s + ln < n:
                out[s:s + ln] += 0.05 * rng.uniform(-1, 1, ln) * np.exp(-np.arange(ln) / SR * 120)
    out = _lp_fast(out, 5200)
    out = out[:int(duration * SR)]
    # fade in/out
    fi, fo = int(0.4 * SR), int(1.2 * SR)
    out[:fi] *= np.linspace(0, 1, fi); out[-fo:] *= np.linspace(1, 0, fo)
    out /= (np.max(np.abs(out)) + 1e-9)
    return out.astype(np.float32), {"bpm": bpm, "root": root, "minor": scale is MINOR}


def duck(music, voice, sr=SR, depth_db=9.0, attack=0.04, release=0.35):
    """Lower the music while the voice is speaking (simple sidechain)."""
    from scipy.signal import lfilter
    env = np.abs(voice)
    win = int(0.03 * sr)
    env = np.convolve(env, np.ones(win) / win, mode="same")
    gate = (env > 0.02).astype(float)
    a_att = np.exp(-1 / (attack * sr)); a_rel = np.exp(-1 / (release * sr))
    smooth = np.empty_like(gate); acc = 0.0
    # asymmetric smoothing, vectorised enough for 20 s clips
    for i in range(len(gate)):
        a = a_att if gate[i] > acc else a_rel
        acc = a * acc + (1 - a) * gate[i]
        smooth[i] = acc
    gain = 10 ** (-depth_db * smooth / 20)
    return music * gain
