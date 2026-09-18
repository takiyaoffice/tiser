#!/usr/bin/env python3
"""
ティザー（FUTURE FANTASY ─未来の地図─）で使うアセットを書き出す。

  assets/img/hero/scene.webp   背景（文字の無い風景画）
  assets/img/hero/crest.webp   60TH の盾
  assets/img/hero/logo.webp    FUTURE FANTASY エンブレム
  assets/img/hero/lead.webp    60年の軌跡、…／舞台は仙台。
  assets/img/hero/date.webp    2027.1.22-24
  assets/img/hero/coming.webp  A new adventure is coming…
  assets/img/icon-*.png        PWA アイコン
  assets/img/clouds.png        空を流れる雲のテクスチャ
  assets/img/splash/*.png      iOS の起動画像

元素材（assets/img/parts/）は書き換えない。

使い方:  python3 tools/make_hero.py
必要なもの:  pip install Pillow numpy opencv-python-headless
"""

from __future__ import annotations

import pathlib

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent.parent
IMG = ROOT / "assets" / "img"
PARTS = IMG / "parts"
HERO = IMG / "hero"

# 書き出す幅。表示サイズの約 2 倍を確保している
#   画面幅 853 のときの表示幅 → その 2 倍
SIZES = {
    "crest": 320,   # 表示 13.6% (116px)
    "logo": 1200,   # 表示 60.8% (519px)
    "lead": 1280,   # 表示 65.2% (556px)
    "date": 760,    # 表示 37.4% (319px)
    "coming": 1080,  # 表示 54.5% (465px)
}


def trim(im: Image.Image, thr: int = 8) -> Image.Image:
    """透明な余白を落とす。"""
    box = im.getchannel("A").point(lambda v: 255 if v > thr else 0).getbbox()
    return im.crop(box) if box else im


def to_width(im: Image.Image, w: int) -> Image.Image:
    if im.width == w:
        return im
    return im.resize((w, max(1, round(im.height * w / im.width))), Image.LANCZOS)


def save(im: Image.Image, name: str, quality: int = 92) -> None:
    HERO.mkdir(parents=True, exist_ok=True)
    path = HERO / f"{name}.webp"
    im.save(path, "WEBP", quality=quality, method=6)
    print(f"  hero/{name + '.webp':<14} {im.width:5d}x{im.height:<5d} "
          f"縦横比 {im.width / im.height:.3f}  {path.stat().st_size / 1024:6.1f} KB")


# ---------------------------------------------------------------------------
def build_scene() -> None:
    """背景。縦長の原寸をそのまま WebP にする。"""
    im = Image.open(PARTS / "scene-base.png").convert("RGB")
    HERO.mkdir(parents=True, exist_ok=True)
    path = HERO / "scene.webp"
    im.save(path, "WEBP", quality=90, method=6)
    print(f"  hero/scene.webp   {im.width}x{im.height}  {path.stat().st_size / 1024:.0f} KB")


def build_parts() -> None:
    for name, src in (("crest", "emblem-60th.png"),
                      ("logo", "emblem-future-fantasy.png"),
                      ("date", "date-2027.png")):
        im = trim(Image.open(PARTS / src).convert("RGBA"))
        save(to_width(im, SIZES[name]), name)


def build_lead() -> None:
    """リード文は 2 行なので、1 行ずつ出せるよう上下に切り分ける。"""
    im = trim(Image.open(PARTS / "lead-sendai.png").convert("RGBA"))
    alpha = np.asarray(im.getchannel("A"), dtype=np.float32) / 255.0

    # 行間（横一列がほぼ透明な帯）を探す
    rows = alpha.mean(axis=1)
    mid = len(rows) // 2
    lo, hi = int(len(rows) * 0.35), int(len(rows) * 0.65)
    split = lo + int(np.argmin(rows[lo:hi]))

    full_w = im.width
    for idx, (y0, y1) in enumerate(((0, split), (split, im.height)), start=1):
        line = trim(im.crop((0, y0, im.width, y1)))
        # 元の行頭位置を保つため、切り出し前の左右位置を記録しておく
        box = im.crop((0, y0, im.width, y1)).getchannel("A") \
                .point(lambda v: 255 if v > 8 else 0).getbbox()
        w = round(SIZES["lead"] * (box[2] - box[0]) / full_w)
        save(to_width(line, w), f"lead{idx}")
        print(f"      行{idx}: 元画像内の左端 {box[0] / full_w:.3f}  幅 {(box[2] - box[0]) / full_w:.3f}")


def build_coming() -> None:
    """「A new adventure is coming…」を最初のポスターから切り出す。

    暗い空に明るい文字が乗っているので、周囲との明暗差をそのまま
    透明度にすれば、背景の無い一行として取り出せる。
    """
    src = Image.open(IMG / "teaser-source.png").convert("RGB")
    box = (160, 722, 706, 790)
    crop = np.asarray(src.crop(box)).astype(np.float32)

    gray = cv2.cvtColor(crop.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
    bg = cv2.medianBlur(gray.astype(np.uint8), 41).astype(np.float32)
    alpha = np.clip((gray - bg - 4) / 70.0, 0, 1) ** 0.85

    # 文字の色そのものを残す（暗い縁を持ち込まない）
    rgb = np.clip(crop * 1.04, 0, 255)

    out = np.dstack([rgb, alpha * 255]).astype(np.uint8)
    im = trim(Image.fromarray(out, "RGBA"), thr=6)
    save(to_width(im, SIZES["coming"]), "coming")


# ---------------------------------------------------------------------------
def fbm(width: int, height: int, beta: float, seed: int, stretch: float = 1.0) -> np.ndarray:
    """FFT によるスペクトル合成。上下左右に完全ループするノイズを返す。"""
    rng = np.random.default_rng(seed)
    spec = np.fft.fft2(rng.normal(size=(height, width)))

    fy = np.fft.fftfreq(height)[:, None]
    fx = np.fft.fftfreq(width)[None, :] * stretch
    radius = np.sqrt(fx ** 2 + fy ** 2)
    radius[0, 0] = 1.0

    spec *= 1.0 / (radius ** beta)
    spec[0, 0] = 0.0

    field = np.real(np.fft.ifft2(spec))
    field -= field.min()
    field /= field.max()
    return field


def build_clouds() -> None:
    w, h = 1024, 512

    base = fbm(w, h, beta=1.85, seed=20261010, stretch=2.6)
    detail = fbm(w, h, beta=1.35, seed=1011, stretch=3.2)
    field = base * 0.72 + detail * 0.42

    # 行ごとに正規化する。
    # こうしないと濃い帯が特定の高さに居座り、文字の上に霞をかけてしまう。
    field = (field - field.mean(axis=1, keepdims=True)) / (field.std(axis=1, keepdims=True) + 1e-6)

    alpha = 1.0 / (1.0 + np.exp(-(field - 0.75) * 1.9))
    alpha = np.clip((alpha - 0.10) / 0.78, 0.0, 1.0) ** 1.15

    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., 0] = 255
    rgba[..., 1] = 242
    rgba[..., 2] = 220
    rgba[..., 3] = (alpha * 255).astype(np.uint8)

    img = Image.fromarray(rgba, "RGBA").filter(ImageFilter.GaussianBlur(0.8))
    out = IMG / "clouds.png"
    img.save(out, optimize=True)
    print(f"clouds.png  : {out.stat().st_size / 1024:.0f} KB  ({w}x{h})")


# ---------------------------------------------------------------------------
def build_icons() -> None:
    """アイコンは 60TH の盾を使う。"""
    shield = trim(Image.open(PARTS / "emblem-60th.png").convert("RGBA"), thr=70)

    for size, name in ((512, "icon-512.png"), (192, "icon-192.png"), (180, "apple-touch-icon.png")):
        canvas = Image.new("RGB", (size, size), (8, 10, 16))
        art = to_width(shield, int(size * 0.62))
        if art.height > size * 0.82:
            art = art.resize((max(1, round(art.width * size * 0.82 / art.height)), int(size * 0.82)), Image.LANCZOS)
        canvas.paste(art, ((size - art.width) // 2, (size - art.height) // 2), art)
        canvas.save(IMG / name, optimize=True)

    size = 512
    canvas = Image.new("RGB", (size, size), (8, 10, 16))
    art = to_width(shield, int(size * 0.44))
    canvas.paste(art, ((size - art.width) // 2, (size - art.height) // 2), art)
    canvas.save(IMG / "icon-maskable-512.png", optimize=True)
    canvas.resize((64, 64), Image.LANCZOS).save(IMG / "favicon.png", optimize=True)
    print("  icon-*.png       生成")


SPLASH_SIZES = [
    (1290, 2796, 430, 932, 3), (1179, 2556, 393, 852, 3), (1284, 2778, 428, 926, 3),
    (1170, 2532, 390, 844, 3), (1125, 2436, 375, 812, 3), (1242, 2688, 414, 896, 3),
    (828, 1792, 414, 896, 2), (750, 1334, 375, 667, 2), (1242, 2208, 414, 736, 3),
    (1620, 2160, 810, 1080, 2),
]


def build_splash() -> None:
    """起動直後の黒画面に、60TH だけが浮かぶ絵。演出の 1 コマ目と揃える。"""
    shield = trim(Image.open(PARTS / "emblem-60th.png").convert("RGBA"), thr=8)
    out_dir = IMG / "splash"
    out_dir.mkdir(exist_ok=True)

    total = 0
    for w, h, *_ in SPLASH_SIZES:
        canvas = Image.new("RGB", (w, h), (5, 6, 10))
        art = to_width(shield, int(w * 0.30))
        canvas.paste(art, ((w - art.width) // 2, int(h * 0.40) - art.height // 2), art)
        path = out_dir / f"splash-{w}x{h}.png"
        canvas.convert("P", palette=Image.ADAPTIVE, colors=96).save(path, optimize=True)
        total += path.stat().st_size
    print(f"  splash/*.png     {len(SPLASH_SIZES)} 枚 / 合計 {total / 1024:.0f} KB")


def main() -> None:
    print("素材を書き出します")
    build_scene()
    build_parts()
    build_lead()
    build_coming()
    build_clouds()
    build_icons()
    build_splash()


if __name__ == "__main__":
    main()
