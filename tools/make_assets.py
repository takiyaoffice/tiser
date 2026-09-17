#!/usr/bin/env python3
"""
ティザー画面で使う派生アセットを生成するスクリプト。

  * assets/img/teaser.webp  : 元ポスター画像の高画質 WebP（見た目は等価・転送量削減）
  * assets/img/clouds.png   : 横方向にシームレスな fBm 雲テクスチャ（雲の流れ表現用）
  * assets/img/icon-*.png   : PWA 用アイコン
  * assets/img/splash-bg.png: 起動時の下地（単色に近い背景）

元画像 assets/img/teaser.png は一切加工しない（構図・文字・色をそのまま使うため）。

使い方:  python3 tools/make_assets.py
"""

from __future__ import annotations

import pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent.parent
IMG = ROOT / "assets" / "img"
SRC = IMG / "teaser.png"


def build_webp() -> None:
    im = Image.open(SRC).convert("RGB")
    out = IMG / "teaser.webp"
    im.save(out, "WEBP", quality=94, method=6)
    print(f"teaser.webp : {out.stat().st_size / 1024:.0f} KB  ({im.size[0]}x{im.size[1]})")


def fbm(width: int, height: int, beta: float, seed: int, stretch: float = 1.0) -> np.ndarray:
    """FFT によるスペクトル合成。上下左右に完全ループするノイズを返す。

    stretch > 1 で横方向に引き伸ばされた（＝流れているような）模様になる。
    """
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

    # 低周波（大きな雲塊）と高周波（ちぎれ雲）を重ねる
    base = fbm(w, h, beta=1.85, seed=20261010, stretch=2.6)
    detail = fbm(w, h, beta=1.35, seed=1011, stretch=3.2)
    field = base * 0.72 + detail * 0.42

    # 行ごとに正規化する。
    # こうしないと濃い帯が特定の高さに居座り、文字の上に霞をかけてしまう。
    field = (field - field.mean(axis=1, keepdims=True)) / (field.std(axis=1, keepdims=True) + 1e-6)

    # 濃淡をなだらかに。平均が薄く、ところどころ濃い、という分布にする
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


def build_icons() -> None:
    src = Image.open(SRC).convert("RGB")

    # 地図アイコン周辺を正方形に切り出してアイコンの主役にする
    box = (322, 818, 538, 1010)
    crop = src.crop(box)

    for size, name in ((512, "icon-512.png"), (192, "icon-192.png"), (180, "apple-touch-icon.png")):
        canvas = Image.new("RGB", (size, size), (10, 8, 6))
        scale = (size * 0.78) / max(crop.size)
        art = crop.resize((max(1, int(crop.width * scale)), max(1, int(crop.height * scale))), Image.LANCZOS)
        canvas.paste(art, ((size - art.width) // 2, (size - art.height) // 2))

        # 金の細枠を足してアプリアイコンらしく整える
        draw = ImageDraw.Draw(canvas)
        pad = max(2, size // 22)
        draw.rounded_rectangle(
            (pad, pad, size - pad - 1, size - pad - 1),
            radius=size // 9,
            outline=(176, 139, 70),
            width=max(1, size // 96),
        )
        canvas.save(IMG / name, optimize=True)
        print(f"{name:<18}: {(IMG / name).stat().st_size / 1024:.0f} KB")

    # マスカブルアイコン（余白を多めに取る）
    size = 512
    canvas = Image.new("RGB", (size, size), (10, 8, 6))
    scale = (size * 0.52) / max(crop.size)
    art = crop.resize((int(crop.width * scale), int(crop.height * scale)), Image.LANCZOS)
    canvas.paste(art, ((size - art.width) // 2, (size - art.height) // 2))
    canvas.save(IMG / "icon-maskable-512.png", optimize=True)
    print(f"icon-maskable-512  : {(IMG / 'icon-maskable-512.png').stat().st_size / 1024:.0f} KB")

    # favicon
    canvas.resize((64, 64), Image.LANCZOS).save(IMG / "favicon.png", optimize=True)


# iPhone の主要解像度（幅, 高さ, 論理幅, 論理高さ, 倍率）
SPLASH_SIZES = [
    (1290, 2796, 430, 932, 3),
    (1179, 2556, 393, 852, 3),
    (1284, 2778, 428, 926, 3),
    (1170, 2532, 390, 844, 3),
    (1125, 2436, 375, 812, 3),
    (1242, 2688, 414, 896, 3),
    (828, 1792, 414, 896, 2),
    (750, 1334, 375, 667, 2),
    (1242, 2208, 414, 736, 3),
    (1620, 2160, 810, 1080, 2),
]


def build_splash() -> None:
    """PWA 起動時の白画面を避けるための、暗い起動画像。

    ポスターそのものではなく、地図アイコンだけを置いた静かな画にする。
    こうすると容量が小さく、本編のフェードインへ自然につながる。
    """
    src = Image.open(SRC).convert("RGB")
    art = src.crop((322, 818, 538, 1010))

    out_dir = IMG / "splash"
    out_dir.mkdir(exist_ok=True)

    total = 0
    for w, h, *_ in SPLASH_SIZES:
        canvas = Image.new("RGB", (w, h), (10, 8, 6))
        scale = (w * 0.34) / art.width
        piece = art.resize((int(art.width * scale), int(art.height * scale)), Image.LANCZOS)

        # 端をなじませてから中央に置く
        mask = Image.new("L", piece.size, 0)
        ImageDraw.Draw(mask).rectangle(
            (piece.width * 0.03, piece.height * 0.03,
             piece.width * 0.97, piece.height * 0.97), fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(piece.width * 0.05))
        canvas.paste(piece, ((w - piece.width) // 2, (h - piece.height) // 2), mask)

        path = out_dir / f"splash-{w}x{h}.png"
        canvas.convert("P", palette=Image.ADAPTIVE, colors=128).save(path, optimize=True)
        total += path.stat().st_size

    print(f"splash/*.png: {len(SPLASH_SIZES)} 枚 / 合計 {total / 1024:.0f} KB")


def splash_links() -> str:
    """index.html に貼る link タグを組み立てる（生成結果を貼り付けて使う）"""
    lines = []
    for w, h, lw, lh, ratio in SPLASH_SIZES:
        lines.append(
            '<link rel="apple-touch-startup-image" '
            f'media="(device-width: {lw}px) and (device-height: {lh}px) '
            f'and (-webkit-device-pixel-ratio: {ratio}) and (orientation: portrait)" '
            f'href="assets/img/splash/splash-{w}x{h}.png">'
        )
    return "\n".join(lines)


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"元画像が見つかりません: {SRC}")
    build_webp()
    build_clouds()
    build_icons()
    build_splash()


if __name__ == "__main__":
    main()
