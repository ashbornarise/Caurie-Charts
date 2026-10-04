"""Papier déchiré et texture de papier générés par programme (nos propres fichiers : aucune licence tierce).

  python -m core.services.social.papier   → régénère resources/papier/ (bas.png, bout-8/9/12.png, texture.jpg)
Bord déchiré : bruit fractal (grandes ondulations + dents fines), liseré de fibres blanches, ombre portée douce.
"""
import numpy as np
from PIL import Image, ImageFilter

from core.services.social import image as PI

OUT = PI.REPO / "resources" / "papier"
PAPER = np.array([246, 246, 249], np.float32)


def _noise1d(n, rng, octaves=((0.004, 1.0), (0.02, 0.45), (0.09, 0.18), (0.35, 0.07))):
    """Bruit 1D fractal normalisé (-1..1)."""
    x = np.arange(n, dtype=np.float32)
    out = np.zeros(n, np.float32)
    for freq, amp in octaves:
        pts = rng.uniform(-1, 1, int(n * freq) + 3)
        out += amp * np.interp(x * freq, np.arange(len(pts)), pts)
    return out / np.abs(out).max()


def texture(w, h, seed=7) -> Image.Image:
    """Papier blanc légèrement fibreux (grain fin + nuages très doux)."""
    rng = np.random.default_rng(seed)
    fine = rng.normal(0, 1, (h, w)).astype(np.float32)
    small = Image.fromarray(((rng.normal(0, 1, (h // 24 + 1, w // 24 + 1)) + 3) * 40).clip(0, 255).astype(np.uint8))
    clouds = (np.asarray(small.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(30)), np.float32) / 40 - 3)
    fib = Image.fromarray(((rng.normal(0, 1, (h, w)) + 3) * 40).clip(0, 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(1))
    fib = np.asarray(fib.resize((w, h)).filter(ImageFilter.GaussianBlur(0.6)), np.float32) / 40 - 3
    val = PAPER[None, None, :] + (fine * 2.2 + clouds * 2.5 + fib * 1.6)[..., None]
    return Image.fromarray(val.clip(0, 255).astype(np.uint8), "RGB")


def torn(w, h, edges="tb", seed=1, amp=0.035, shadow=True) -> Image.Image:
    """Feuille RGBA de w × h (dans un cadre avec marge pour l'ombre) ; edges : bords déchirés parmi t, b, l, r."""
    rng = np.random.default_rng(seed)
    m = int(max(w, h) * 0.05)
    W, H = w + 2 * m, h + 2 * m
    a = np.zeros((H, W), np.float32)
    ys, xs = np.mgrid[0:H, 0:W]
    top = np.full(W, m, np.float32)
    bot = np.full(W, m + h, np.float32)
    left = np.full(H, m, np.float32)
    right = np.full(H, m + w, np.float32)
    A = amp * h if h < w else amp * w
    if "t" in edges:
        top = m + A + _noise1d(W, rng) * A
    if "b" in edges:
        bot = m + h - A + _noise1d(W, rng) * A
    if "l" in edges:
        left = m + A + _noise1d(H, rng) * A
    if "r" in edges:
        right = m + w - A + _noise1d(H, rng) * A
    inside = (ys >= top[None, :]) & (ys <= bot[None, :]) & (xs >= left[:, None]) & (xs <= right[:, None])
    a[inside] = 1
    # distance approximative au bord déchiré (pour le liseré de fibres)
    d = np.minimum.reduce([ys - top[None, :] if "t" in edges else np.full((H, W), 1e6),
                           bot[None, :] - ys if "b" in edges else np.full((H, W), 1e6),
                           xs - left[:, None] if "l" in edges else np.full((H, W), 1e6),
                           right[:, None] - xs if "r" in edges else np.full((H, W), 1e6)]).astype(np.float32)
    tex = np.asarray(texture(W, H, seed + 11), np.float32)
    rim = np.clip(1 - d / max(3, A * 0.22), 0, 1)
    fibers = rng.uniform(0.6, 1.0, (H, W)).astype(np.float32)
    tex = tex * (1 - rim[..., None] * 0.6) + 255 * rim[..., None] * 0.6 * fibers[..., None]
    alpha = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7))
    al = np.asarray(alpha, np.float32) / 255
    al = np.where(rim > 0.6, al * fibers ** 0.5, al)
    sheet = np.dstack([tex.clip(0, 255), al * 255]).astype(np.uint8)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if shadow:
        sh = Image.fromarray((a * 70).astype(np.uint8)).filter(ImageFilter.GaussianBlur(max(4, m * 0.18)))
        layer = Image.new("RGBA", (W, H), (20, 18, 40, 0))
        layer.putalpha(sh)
        out.alpha_composite(layer, (int(m * 0.08), int(m * 0.22)))
    out.alpha_composite(Image.fromarray(sheet, "RGBA"))
    # Côtés non déchirés : coupés net au ras de la feuille (bandeau pleine largeur, feuille qui touche le bas)
    box = list(out.getbbox())
    if "l" not in edges:
        box[0] = m
    if "r" not in edges:
        box[2] = m + w
    if "t" not in edges:
        box[1] = m
    if "b" not in edges:
        box[3] = m + h
    return out.crop(tuple(box))


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    texture(2160, 2160).save(OUT / "texture.jpg", quality=88)
    torn(2160, 1300, "t", seed=3, amp=0.018).save(OUT / "bas.png", optimize=True)
    torn(1050, 300, "tblr", seed=5, amp=0.06).save(OUT / "bout-9.png", optimize=True)
    torn(1100, 420, "tb", seed=9, amp=0.05).save(OUT / "bout-12.png", optimize=True)
    torn(1000, 560, "tblr", seed=13, amp=0.05).save(OUT / "bout-8.png", optimize=True)


if __name__ == "__main__":
    build()
