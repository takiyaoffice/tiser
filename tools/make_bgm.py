#!/usr/bin/env python3
"""
ティザー画面の BGM を合成する。

  assets/audio/theme.mp3   64秒・繰り返し再生できる主題

外部の音源は使わず、すべて数値計算で作っている。

構成（60 BPM・1小節 4秒・全16小節）
  1   Dm    低い持続音と空気の音だけ。黒画面に 60TH が浮かぶところ
  2   Dm    和音がふくらむ。背景が現れ、6.3 秒あたりで鐘が一度鳴る
  3   B♭    文字が出はじめる
  4   F     ひと息つく
  5-8 F C   主題の前置き
  9-12 Dm B♭ F C   鐘で旋律
  13-16 Gm B♭ C Dm  戻って、頭へつながる

使い方:  python3 tools/make_bgm.py
必要なもの:  pip install numpy scipy imageio-ffmpeg
"""

from __future__ import annotations

import pathlib
import subprocess

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 44100
BPM = 60.0
BAR = 4 * 60.0 / BPM          # 4 秒
BARS = 16
LOOP = BAR * BARS             # 64 秒
TAIL = 7.0                    # 残響のぶんだけ長く作り、頭へ巻き戻す

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "audio"

# ---------------------------------------------------------------------------
# 音名 → 周波数
# ---------------------------------------------------------------------------
NAMES = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6,
         "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def hz(note: str) -> float:
    """'A4' や 'Bb3' を周波数に。"""
    name = note[:-1].replace("b", "#") if note[1:2] == "b" else note[:-1]
    if note[1:2] == "b":                       # B♭ → A#
        name = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}[note[:2]]
    octave = int(note[-1])
    return 440.0 * 2 ** ((NAMES[name] + (octave - 4) * 12 - 9) / 12)


# 和音の並び（1小節ずつ）
PROGRESSION = [
    ("Dm", ["D3", "F3", "A3"]),
    ("Dm", ["D3", "F3", "A3"]),
    ("Bb", ["D3", "F3", "Bb3"]),
    ("F",  ["C3", "F3", "A3"]),

    ("F",  ["C3", "F3", "A3"]),
    ("F",  ["C3", "F3", "A3"]),
    ("C",  ["C3", "E3", "G3"]),
    ("C",  ["C3", "E3", "G3"]),

    ("Dm", ["D3", "F3", "A3"]),
    ("Bb", ["D3", "F3", "Bb3"]),
    ("F",  ["C3", "F3", "A3"]),
    ("C",  ["C3", "E3", "G3"]),

    ("Gm", ["D3", "G3", "Bb3"]),
    ("Bb", ["D3", "F3", "Bb3"]),
    ("C",  ["C3", "E3", "G3"]),
    ("Dm", ["D3", "F3", "A3"]),
]

BASS = ["D2", "D2", "Bb1", "F2", "F2", "F2", "C2", "C2",
        "D2", "Bb1", "F2", "C2", "G1", "Bb1", "C2", "D2"]

# 小節ごとの音量。静かに始まり、中ほどでふくらみ、また静かに戻って頭へつながる
DYNAMICS = [0.30, 0.36, 0.42, 0.44,
            0.44, 0.44, 0.44, 0.44,
            0.46, 0.46, 0.46, 0.44,
            0.42, 0.38, 0.33, 0.28]

# 鐘の旋律（時刻[秒], 音, 強さ）
MELODY = [
    (0.60, "D5", 0.22),      # 黒画面。遠くで一度だけ
    (6.30, "D5", 0.52),      # エンブレムが着地する瞬間
    (7.10, "A4", 0.30),
    (9.00, "F4", 0.26),
    (11.40, "A4", 0.24),
    (13.30, "D4", 0.22),

    (32.0, "A4", 0.34), (33.6, "F4", 0.24),
    (36.0, "D4", 0.32),
    (40.0, "C5", 0.34), (41.6, "A4", 0.24),
    (44.0, "G4", 0.30),
    (48.0, "Bb4", 0.34), (49.6, "D5", 0.26),
    (52.0, "F4", 0.28),
    (56.0, "A4", 0.22),
    (60.0, "D4", 0.18),
]


# ---------------------------------------------------------------------------
# 部品
# ---------------------------------------------------------------------------
def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * SR), dtype=np.float32)


def add(buf: np.ndarray, part: np.ndarray, at: float) -> None:
    i = int(at * SR)
    n = min(len(part), len(buf) - i)
    if n > 0:
        buf[i:i + n] += part[:n]


def env_adsr(n: int, attack: float, decay: float, sustain: float, release: float) -> np.ndarray:
    a, d, r = int(attack * SR), int(decay * SR), int(release * SR)
    s = max(0, n - a - d - r)
    return np.concatenate([
        np.linspace(0, 1, a, endpoint=False) ** 1.6 if a else np.array([]),
        np.linspace(1, sustain, d, endpoint=False) if d else np.array([]),
        np.full(s, sustain),
        np.linspace(sustain, 0, r) ** 1.4 if r else np.array([]),
    ])[:n].astype(np.float32)


def highpass(x: np.ndarray, cutoff: float, order: int = 2) -> np.ndarray:
    sos = butter(order, cutoff, "high", fs=SR, output="sos")
    return sosfilt(sos, x).astype(np.float32)


def lowpass(x: np.ndarray, cutoff: float, order: int = 4) -> np.ndarray:
    sos = butter(order, min(cutoff, SR * 0.45), "low", fs=SR, output="sos")
    return sosfilt(sos, x).astype(np.float32)


def bandpass(x: np.ndarray, lo: float, hi: float, order: int = 2) -> np.ndarray:
    sos = butter(order, [lo, min(hi, SR * 0.45)], "band", fs=SR, output="sos")
    return sosfilt(sos, x).astype(np.float32)


def pad_voice(freqs, seconds: float, gain: float, bright: float = 1.0) -> np.ndarray:
    """重ねた弦のような持続音。少しずつ調子の外れた声を足して厚みを出す。"""
    n = int(seconds * SR)
    t = np.arange(n) / SR
    out = np.zeros(n, dtype=np.float32)

    for f in freqs:
        for cents, level in ((-7.0, 0.5), (0.0, 1.0), (6.0, 0.5)):
            fd = f * 2 ** (cents / 1200)
            # 倍音を少しずつ弱めながら重ねる
            for k, amp in ((1, 1.0), (2, 0.38), (3, 0.18), (4, 0.09), (5, 0.05)):
                drift = 1 + 0.0016 * np.sin(2 * np.pi * (0.07 + 0.013 * k) * t + k)
                out += (level * amp * np.sin(2 * np.pi * fd * k * t * drift)).astype(np.float32)

    out /= max(1.0, len(freqs) * 2.6)
    out = lowpass(out, 900 * bright + 260)
    return (out * gain).astype(np.float32)


def bell(freq: float, gain: float, seconds: float = 6.0) -> np.ndarray:
    """FM による鐘。倍音が整数比から外れているので金属らしく響く。"""
    n = int(seconds * SR)
    t = np.arange(n) / SR

    mod_index = 3.9 * np.exp(-t * 2.9)
    mod = np.sin(2 * np.pi * freq * 1.41 * t) * mod_index
    tone = np.sin(2 * np.pi * freq * t + mod)

    body = np.sin(2 * np.pi * freq * t) * 0.55 + np.sin(2 * np.pi * freq * 2 * t) * 0.16
    decay = np.exp(-t * 0.72) * (1 - np.exp(-t * 140))

    out = (tone * 0.48 + body * 1.15) * decay
    return (lowpass(out, 3400) * gain).astype(np.float32)


def sub_note(freq: float, seconds: float, gain: float) -> np.ndarray:
    n = int(seconds * SR)
    t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * freq * t) + 0.30 * np.sin(2 * np.pi * freq * 2 * t) \
        + 0.10 * np.sin(2 * np.pi * freq * 3 * t)
    return (tone * env_adsr(n, 0.9, 0.4, 0.82, 1.4) * gain).astype(np.float32)


def air(seconds: float, gain: float, seed: int) -> np.ndarray:
    """風のような空気の層。ゆっくり寄せては引く。"""
    n = int(seconds * SR)
    rng = np.random.default_rng(seed)
    noise = rng.normal(size=n).astype(np.float32)
    noise = bandpass(noise, 170, 2400)

    t = np.arange(n) / SR
    swell = (0.55 + 0.45 * np.sin(2 * np.pi * t / 16.0 - 1.2)) \
        * (0.7 + 0.3 * np.sin(2 * np.pi * t / 5.3))
    return (noise * swell * gain).astype(np.float32)


def shimmer(seconds: float, gain: float, seed: int) -> np.ndarray:
    """光の粒に合わせた、ごく small な高音のきらめき。"""
    n = int(seconds * SR)
    out = np.zeros(n, dtype=np.float32)
    rng = np.random.default_rng(seed)

    scale = [hz(x) for x in ("D6", "F6", "A6", "D7", "A5")]
    at = 1.5
    while at < seconds - 1:
        f = scale[rng.integers(len(scale))]
        d = 1.6 + rng.random() * 1.4
        m = int(d * SR)
        t = np.arange(m) / SR
        tone = np.sin(2 * np.pi * f * t) * np.exp(-t * 3.2) * (1 - np.exp(-t * 90))
        add(out, (tone * (0.5 + rng.random() * 0.5)).astype(np.float32), at)
        at += 2.4 + rng.random() * 4.0

    return (out * gain).astype(np.float32)


def pedal(seconds: float, gain: float) -> np.ndarray:
    """途切れない低い持続音。繰り返しの継ぎ目をまたいで鳴り続ける。

    ゆらぎの周期を 16 秒（全体 64 秒の約数）にしてあるので、
    頭に戻ったときも音量がそろう。
    """
    n = int(seconds * SR)
    t = np.arange(n) / SR
    f = hz("D2")
    tone = (np.sin(2 * np.pi * f * t)
            + 0.30 * np.sin(2 * np.pi * f * 2 * t)
            + 0.16 * np.sin(2 * np.pi * f * 0.5 * t))
    swell = 0.80 + 0.20 * np.sin(2 * np.pi * t / 16.0)
    return (tone * swell * gain).astype(np.float32)


def impulse_response(seconds: float, seed: int, decay: float) -> np.ndarray:
    """残響用のインパルス応答。減衰しながら、だんだん暗くなる雑音。"""
    n = int(seconds * SR)
    rng = np.random.default_rng(seed)
    t = np.arange(n) / SR

    ir = rng.normal(size=n).astype(np.float32) * np.exp(-t * decay)
    ir[: int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))   # 直接音は抑える
    ir = lowpass(ir, 4200)
    ir += lowpass(rng.normal(size=n).astype(np.float32) * np.exp(-t * decay * 0.6), 1100) * 0.6
    return (ir / np.abs(ir).max()).astype(np.float32)


def reverb(x: np.ndarray, ir: np.ndarray, mix: float) -> np.ndarray:
    wet = fftconvolve(x, ir)[: len(x)].astype(np.float32)
    wet /= max(1e-6, np.abs(wet).max())
    wet *= np.abs(x).max()
    return ((1 - mix) * x + mix * wet).astype(np.float32)


# ---------------------------------------------------------------------------
def build() -> np.ndarray:
    total = LOOP + TAIL

    pads = silence(total)
    bells = silence(total)
    lows = silence(total)

    # 和音。小節をまたいで重ねることで、切れ目が出ないようにする
    for i, (_, notes) in enumerate(PROGRESSION):
        at = i * BAR
        gain = DYNAMICS[i]
        voice = pad_voice([hz(x) for x in notes], BAR + 2.6, gain,
                          bright=0.6 if (i < 2 or i >= 14) else 1.0)
        # 先頭の小節は、繰り返しで前の小節から続くので立ち上がりを短くする
        voice *= env_adsr(len(voice), 0.25 if i == 0 else 0.9, 0.8, 0.75, 1.9)
        add(pads, voice, at)

    # 低音
    for i, note in enumerate(BASS):
        g = 0.42 * (DYNAMICS[i] / 0.44)
        add(lows, sub_note(hz(note), BAR + 1.0, g), i * BAR)

    # 鐘
    for at, note, g in MELODY:
        add(bells, bell(hz(note), g), at)

    mix = pads + lows * 1.0 + bells * 0.72 + pedal(total, 0.17)
    mix += lowpass(mix, 230) * 0.24          # 低いところに芯を足す
    mix += air(total, 0.048, seed=7)
    mix += shimmer(total, 0.030, seed=11)

    # 残響。左右で別のインパルス応答を使い、奥行きを作る
    ir_l = impulse_response(2.8, seed=3, decay=2.0)
    ir_r = impulse_response(2.8, seed=4, decay=1.9)
    left = reverb(mix, ir_l, 0.42)
    right = reverb(mix, ir_r, 0.42)

    # 空気の層だけ左右を分ける
    left += air(total, 0.02, seed=21)
    right += air(total, 0.02, seed=22)

    # 耳に聞こえない超低域は落としておく（音量の余裕を食うだけなので）
    left = highpass(left, 32.0)
    right = highpass(right, 32.0)

    stereo = np.stack([left, right], axis=1)

    # 残響のしっぽを頭へ巻き戻して、継ぎ目なく繰り返せるようにする
    loop_n = int(LOOP * SR)
    wrapped = stereo[:loop_n].copy()
    tail = stereo[loop_n:]
    m = min(len(tail), loop_n)
    fade = np.linspace(1, 0, m)[:, None] ** 0.6
    wrapped[:m] += tail[:m] * fade

    # 音量を整える。BGM なので控えめに
    peak = np.abs(wrapped).max()
    wrapped = wrapped / peak * 0.72
    rms = np.sqrt((wrapped ** 2).mean())
    print(f"  ピーク {20 * np.log10(0.72):.1f} dBFS / 実効値 {20 * np.log10(rms):.1f} dBFS")
    return wrapped.astype(np.float32)


def write_mp3(stereo: np.ndarray, path: pathlib.Path, bitrate: str) -> None:
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    pcm = (np.clip(stereo, -1, 1) * 32767).astype("<i2").tobytes()
    path.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error",
         "-f", "s16le", "-ar", str(SR), "-ac", "2", "-i", "pipe:0",
         "-codec:a", "libmp3lame", "-b:a", bitrate, str(path)],
        input=pcm, check=True)

    print(f"  {path.name}  {len(stereo) / SR:.1f}秒  {path.stat().st_size / 1024:.0f} KB  ({bitrate})")


def main() -> None:
    print("BGM を合成します")
    stereo = build()
    write_mp3(stereo, OUT_DIR / "theme.mp3", "160k")


if __name__ == "__main__":
    main()
