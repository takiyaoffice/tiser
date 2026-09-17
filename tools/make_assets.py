#!/usr/bin/env python3
"""
ティザー画面で使うアセットを生成するスクリプト。

  * assets/img/teaser.png    : 配信用ポスター（原画の日付だけを差し替えたもの）
  * assets/img/teaser.webp   : 同じ絵の WebP 版（転送量削減）
  * assets/img/plate/*.webp  : 文字が出てくる前の「文字が無い状態」の当て板
  * assets/img/clouds.png    : 横方向にシームレスな fBm 雲テクスチャ
  * assets/img/icon-*.png    : PWA 用アイコン
  * assets/img/splash/*.png  : iOS の起動画像

原画 assets/img/teaser-source.png は決して書き換えない。
日付の差し替えも、当て板の生成も、すべてこのスクリプトから再現できる。

使い方:  python3 tools/make_assets.py
必要なもの:  pip install Pillow numpy opencv-python-headless
"""

from __future__ import annotations

import pathlib

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
IMG = ROOT / "assets" / "img"
SRC = IMG / "teaser-source.png"     # 原画（無加工）
POSTER = IMG / "teaser.png"         # 配信用（日付差し替え済み）

FONT = "/mnt/skills/examples/canvas-design/canvas-fonts/Gloock-Regular.ttf"

# ---------------------------------------------------------------------------
# 日付の差し替え
# ---------------------------------------------------------------------------
NEW_DATE = "2027.1.22 — 1.24"

# 原画の日付を実測した値（853 x 1844 のピクセル座標）
DATE_INK = (223, 632, 627, 663)     # 文字そのものの範囲
DATE_AREA = (196, 612, 656, 686)    # 消し込みと描き直しを行う範囲
DIGIT_TOP, DIGIT_BOTTOM = 632, 663  # 数字の上端・下端
CELL_DIGIT, CELL_DOT = 26.0, 14.0   # 一文字あたりの送り幅
DASH_W, DASH_GAP, DASH_Y, DASH_H = 41, 21, 648, 3
CENTER_X = 426.5
GOLD_TOP = (250, 218, 145)
GOLD_BOTTOM = (200, 160, 90)

# ---------------------------------------------------------------------------
# 文字が出てくる前の「当て板」。文字の範囲は index.html / teaser.js と揃える
# ---------------------------------------------------------------------------
PLATE_PAD = 44

PLATES = [
    # 名前,      文字の範囲,                    消し方,     形態処理のパラメータ
    ("adv",    (180, 184, 680, 236), "ink", dict(open_k=25, thr=4, close_k=9, dil=13)),
    ("jp",     (40, 278, 800, 452), "ink", dict(open_k=45, thr=4, close_k=15, dil=13)),
    ("lead",   (108, 508, 746, 562), "ink", dict(open_k=21, thr=4, close_k=9, dil=13)),
    ("date",   (220, 626, 634, 670), "ink", dict(open_k=21, thr=4, close_k=9, dil=13)),
    ("coming", (174, 732, 692, 778), "ink", dict(open_k=21, thr=3, close_k=9, dil=13)),
    ("map",    (316, 826, 546, 1006), "area", dict()),
    ("tag",    (128, 1622, 722, 1672), "ink", dict(open_k=21, thr=4, close_k=9, dil=13)),
]


# ===========================================================================
# 消し込み
# ===========================================================================
def ink_mask(gray: np.ndarray, box, open_k: int, thr: int, close_k: int, dil: int) -> np.ndarray:
    """文字を塗りつぶしたマスクを作る。

    金色の画そのものだけでなく、その外側に焼き込まれている暗い縁も拾う。
    これを拾わないと、消したあとに文字の影が残ってしまう。
    """
    x0, y0, x1, y1 = box
    sub = gray[y0:y1, x0:x1]
    se = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_k, open_k))

    # opening で「文字が無い状態」を推定 → 明るい側のはみ出しが文字
    bright = cv2.subtract(sub, cv2.morphologyEx(sub, cv2.MORPH_OPEN, se))
    # closing で同様に → 暗い側のはみ出しが影
    dark = cv2.subtract(cv2.morphologyEx(sub, cv2.MORPH_CLOSE, se), sub)

    m = (((bright > thr) | (dark > thr + 2)).astype(np.uint8)) * 255

    # 画数の内側（暗い部分）も含めるため、閉じてから輪郭を塗りつぶす
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE,
                         cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_k, close_k)))
    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(m)
    for c in contours:
        if cv2.contourArea(c) >= 10:
            cv2.drawContours(filled, [c], -1, 255, -1)
    filled = cv2.dilate(filled, np.ones((dil, dil), np.uint8))

    full = np.zeros(gray.shape, np.uint8)
    full[y0:y1, x0:x1] = filled
    return full


def diffuse_fill(bgr: np.ndarray, mask: np.ndarray, rounds: int = 900) -> np.ndarray:
    """穴の外側の色を保ったまま平滑化を繰り返し、滑らかに埋める。

    cv2.inpaint と違って筋が出ないので、地図アイコンのような広い面に使う。
    """
    known = mask == 0
    cur = bgr.astype(np.float32).copy()
    cur[~known] = cur[known].mean(axis=0)
    src = bgr.astype(np.float32)
    for _ in range(rounds):
        cur = cv2.GaussianBlur(cur, (0, 0), 3)
        cur[known] = src[known]
    return np.clip(cur, 0, 255).astype(np.uint8)


def add_grain(filled: np.ndarray, source: np.ndarray, mask: np.ndarray,
              shift: int = 248, amount: float = 0.55) -> np.ndarray:
    """埋めた面が平坦すぎるので、近くの地形のきめだけを借りて戻す。

    左隣の同じ高さから高周波成分だけを取り出して重ねる。
    色や明るさは埋めた結果のままなので、風景としては破綻しない。
    """
    src = source.astype(np.float32)
    detail = src - cv2.GaussianBlur(src, (0, 0), 6)
    detail = np.roll(detail, shift, axis=1)

    m = cv2.GaussianBlur((mask > 0).astype(np.float32), (0, 0), 9)[..., None]
    out = filled.astype(np.float32) + detail * amount * m
    return np.clip(out, 0, 255).astype(np.uint8)


def erase_text(bgr: np.ndarray, tight: np.ndarray, wide: np.ndarray) -> np.ndarray:
    """文字を消す。

    塗り直しの元になる色は、文字の光がおよばない遠くから取りたい（wide）。
    一方で置き換えるのは文字のあった場所だけにしたい（tight）。
    こうすると、文字の周りの雲がそのまま残る。
    """
    filled = cv2.inpaint(bgr, wide, 9, cv2.INPAINT_TELEA).astype(np.float32)
    a = cv2.GaussianBlur((tight > 0).astype(np.float32), (0, 0), 5)[..., None]
    return np.clip(bgr.astype(np.float32) * (1 - a) + filled * a, 0, 255).astype(np.uint8)


# ===========================================================================
# 日付の描き直し
# ===========================================================================
def fit_font():
    target = DIGIT_BOTTOM - DIGIT_TOP + 1
    size = 40
    for _ in range(30):
        f = ImageFont.truetype(FONT, size)
        bb = f.getbbox("2027")
        h = bb[3] - bb[1]
        if h == target:
            return f
        size += 1 if h < target else -1
    return ImageFont.truetype(FONT, size)


def date_mask(text: str, size) -> Image.Image:
    """新しい日付を、原画と同じ送り・同じ高さで並べたマスクを返す。"""
    font = fit_font()
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)

    cells = []
    for ch in text:
        if ch == " ":
            continue
        if ch == "—":
            cells.append((ch, DASH_GAP * 2 + DASH_W))
        else:
            cells.append((ch, CELL_DOT if ch == "." else CELL_DIGIT))

    x = CENTER_X - sum(w for _, w in cells) / 2
    for ch, w in cells:
        if ch == "—":
            x0 = x + DASH_GAP
            draw.rectangle((x0, DASH_Y, x0 + DASH_W - 1, DASH_Y + DASH_H - 1), fill=255)
        else:
            bb = font.getbbox(ch)
            gx = x + (w - (bb[2] - bb[0])) / 2 - bb[0]
            gy = (DIGIT_TOP if ch != "." else DIGIT_BOTTOM - (bb[3] - bb[1])) - bb[1]
            draw.text((gx, gy), ch, font=font, fill=255)
        x += w
    return mask


def draw_date(base: Image.Image, text: str) -> Image.Image:
    mask = date_mask(text, base.size)

    # 原画より少し太いので、わずかに細らせる
    thin = Image.fromarray(cv2.erode(np.asarray(mask), np.ones((2, 2), np.uint8)))
    mask = Image.blend(mask, thin, 0.55)

    m = np.asarray(mask, dtype=np.float32) / 255.0
    h, w = m.shape

    # 金の縦グラデーション
    t = np.clip((np.arange(h) - DIGIT_TOP) / (DIGIT_BOTTOM - DIGIT_TOP), 0, 1)[:, None]
    grad = np.zeros((h, w, 3), np.float32)
    for c in range(3):
        grad[..., c] = GOLD_TOP[c] + (GOLD_BOTTOM[c] - GOLD_TOP[c]) * t

    img = np.asarray(base.convert("RGB"), dtype=np.float32)

    # 文字の下に落ちる、ごく薄い影
    shadow = np.asarray(mask.filter(ImageFilter.GaussianBlur(1.6)), dtype=np.float32) / 255.0
    shadow = np.roll(shadow, 2, axis=0) * 0.30
    img *= (1 - shadow[..., None] * (1 - m[..., None]))

    out = img * (1 - m[..., None]) + grad * m[..., None]
    return Image.fromarray(np.clip(out, 0, 255).astype("uint8"))


def build_poster() -> None:
    src = cv2.imread(str(SRC))
    gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)

    # 古い日付を消す
    mask = ink_mask(gray, DATE_AREA, open_k=31, thr=9, close_k=9, dil=5)
    cleared = cv2.inpaint(src, mask, 9, cv2.INPAINT_TELEA)

    cleared_rgb = Image.fromarray(cv2.cvtColor(cleared, cv2.COLOR_BGR2RGB))
    poster = draw_date(cleared_rgb, NEW_DATE)
    poster.save(POSTER)
    poster.save(IMG / "teaser.webp", "WEBP", quality=94, method=6)

    print(f"teaser.png  : 日付を「{NEW_DATE}」に差し替え")
    print(f"teaser.webp : {(IMG / 'teaser.webp').stat().st_size / 1024:.0f} KB")


# ===========================================================================
# 当て板（文字が出てくる前の状態）
# ===========================================================================
def build_plates() -> None:
    out_dir = IMG / "plate"
    out_dir.mkdir(exist_ok=True)

    poster = cv2.imread(str(POSTER))
    gray = cv2.cvtColor(poster, cv2.COLOR_BGR2GRAY)

    total = 0
    for name, box, method, params in PLATES:
        if method == "ink":
            mask = ink_mask(gray, box, **params)
            wide = dict(params, dil=params["dil"] + 12)
            erased = erase_text(poster, mask, ink_mask(gray, box, **wide))
        else:
            mask = np.zeros(gray.shape, np.uint8)
            x0, y0, x1, y1 = box
            mask[y0:y1, x0:x1] = 255
            erased = add_grain(diffuse_fill(poster, mask), poster, mask)

        # 不透明度は「消した場所」だけ。周囲は元画像そのものなので、
        # ぼかしが外へ広がっても絵は変わらない。
        # 消した範囲を完全に覆うため、ぼかし幅の 2 倍だけ先に太らせる。
        sigma = 16 if method == "area" else 8
        grow = int(round(sigma * 2.5)) * 2 + 1
        alpha = cv2.dilate(mask, np.ones((grow, grow), np.uint8))
        alpha = cv2.GaussianBlur(alpha, (0, 0), sigma)

        pad = PLATE_PAD + (76 if method == "area" else 0)
        x0, y0, x1, y1 = box
        cx0, cy0 = max(0, x0 - pad), max(0, y0 - pad)
        cx1, cy1 = min(poster.shape[1], x1 + pad), min(poster.shape[0], y1 + pad)

        rgb = cv2.cvtColor(erased[cy0:cy1, cx0:cx1], cv2.COLOR_BGR2RGB)
        a = alpha[cy0:cy1, cx0:cx1]
        plate = np.dstack([rgb, a])

        path = out_dir / f"{name}.webp"
        Image.fromarray(plate, "RGBA").save(path, "WEBP", quality=93, method=6)
        total += path.stat().st_size
        print(f"  plate/{name:<7} {cx1 - cx0:4d}x{cy1 - cy0:<4d} "
              f"box=({cx0},{cy0},{cx1},{cy1})  {path.stat().st_size / 1024:5.1f} KB")

    print(f"plate 合計   : {total / 1024:.0f} KB")


# ===========================================================================
# 雲テクスチャ
# ===========================================================================
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


# ===========================================================================
# アイコンと起動画像
# ===========================================================================
def build_icons() -> None:
    src = Image.open(POSTER).convert("RGB")
    crop = src.crop((322, 818, 538, 1010))

    for size, name in ((512, "icon-512.png"), (192, "icon-192.png"), (180, "apple-touch-icon.png")):
        canvas = Image.new("RGB", (size, size), (10, 8, 6))
        scale = (size * 0.78) / max(crop.size)
        art = crop.resize((max(1, int(crop.width * scale)), max(1, int(crop.height * scale))), Image.LANCZOS)
        canvas.paste(art, ((size - art.width) // 2, (size - art.height) // 2))

        draw = ImageDraw.Draw(canvas)
        pad = max(2, size // 22)
        draw.rounded_rectangle(
            (pad, pad, size - pad - 1, size - pad - 1),
            radius=size // 9,
            outline=(176, 139, 70),
            width=max(1, size // 96),
        )
        canvas.save(IMG / name, optimize=True)

    size = 512
    canvas = Image.new("RGB", (size, size), (10, 8, 6))
    scale = (size * 0.52) / max(crop.size)
    art = crop.resize((int(crop.width * scale), int(crop.height * scale)), Image.LANCZOS)
    canvas.paste(art, ((size - art.width) // 2, (size - art.height) // 2))
    canvas.save(IMG / "icon-maskable-512.png", optimize=True)
    canvas.resize((64, 64), Image.LANCZOS).save(IMG / "favicon.png", optimize=True)
    print("icon-*.png  : 生成")


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
    src = Image.open(POSTER).convert("RGB")
    art = src.crop((322, 818, 538, 1010))

    out_dir = IMG / "splash"
    out_dir.mkdir(exist_ok=True)

    total = 0
    for w, h, *_ in SPLASH_SIZES:
        canvas = Image.new("RGB", (w, h), (10, 8, 6))
        scale = (w * 0.34) / art.width
        piece = art.resize((int(art.width * scale), int(art.height * scale)), Image.LANCZOS)

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


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"原画が見つかりません: {SRC}")
    build_poster()
    build_plates()
    build_clouds()
    build_icons()
    build_splash()


if __name__ == "__main__":
    main()
