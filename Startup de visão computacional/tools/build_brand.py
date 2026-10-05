import json
from pathlib import Path

import matplotlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
RULES = json.loads((ROOT / "brand" / "rules.json").read_text(encoding="utf-8"))
PUBLIC = ROOT / "frontend" / "public"
OUT = PUBLIC / "brand"
FONTS = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
COLORS = {"cream": "#f5f1e6", "ink": "#14231e", "beige": "#ede5d8", "red": "#d9432a", "teal": "#3fab94", "tan": "#c9a47a"}

INK = 24


def rgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)


def save_png(array, path):
    mode = "RGBA" if array.shape[2] == 4 else "RGB"
    Image.fromarray(np.round(array).astype(np.uint8), mode).save(path, optimize=True)


def ink_box(crop, background):
    ys, xs = np.nonzero(np.abs(crop - rgb(background)).max(axis=2) > INK)
    return int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())


def plate(sheet, region):
    x0, y0, x1, y1 = region["box"]
    pad = round((y1 - y0) * RULES["clearSpace"])
    crop = sheet[y0 - pad:y1 + pad, x0 - pad:x1 + pad]
    border = np.concatenate([crop[0], crop[-1], crop[:, 0], crop[:, -1]])
    assert (np.abs(border - rgb(region["background"])).sum(axis=1) == 0).all(), "clear space is not pure background"
    top, bottom, left, right = ink_box(crop, region["background"])
    ink = bottom - top + 1
    margin = min(top, crop.shape[0] - 1 - bottom, left, crop.shape[1] - 1 - right)
    assert margin >= RULES["clearSpace"] * ink, "visible ink intrudes on the clear space"
    return crop, [top, bottom, left, right], ink


def icon(sheet, region):
    x0, y0, x1, y1 = region["box"]
    wide = sheet[y0 - 4:y1 + 4, x0 - 4:x1 + 4]
    back = rgb(region["background"])
    vals, counts = np.unique(wide.reshape(-1, 3), axis=0, return_counts=True)
    dark = vals[counts.argmax()].astype(float)
    v = dark - back
    t_wide = ((wide - back) @ v) / (v @ v)
    cy, cx = t_wide.shape[0] // 2, t_wide.shape[1] // 2
    rows = np.nonzero(t_wide[:, cx] > 0.5)[0]
    cols = np.nonzero(t_wide[cy, :] > 0.5)[0]
    top, bottom, left, right = rows.min(), rows.max(), cols.min(), cols.max()
    crop = wide[top - 3:bottom + 4, left - 3:right + 4]
    t = t_wide[top - 3:bottom + 4, left - 3:right + 4]
    h, w, _ = crop.shape
    yy, xx = np.mgrid[0:h, 0:w]
    band = 4
    edge = (np.minimum(yy, h - 1 - yy) <= 3 + band) | (np.minimum(xx, w - 1 - xx) <= 3 + band)
    r = region["cornerRadiusPx"] + band + 3
    corners = ((xx < r) | (xx >= w - r)) & ((yy < r) | (yy >= h - r))
    residual = np.linalg.norm(crop - (back + t[..., None] * v), axis=2)
    mark = (residual > 30) & (t > 0.2)
    assert not (mark & (edge | corners)).any(), "logo mark reaches the edge band"
    matte = edge | corners
    alpha = np.ones((h, w))
    alpha[matte] = np.clip(t[matte], 0, 1)
    color = crop.copy()
    color[matte] = dark
    side = max(h, w)
    square = np.zeros((side, side, 4))
    oy, ox = (side - h) // 2, (side - w) // 2
    square[oy:oy + h, ox:ox + w, :3] = color
    square[oy:oy + h, ox:ox + w, 3] = alpha * 255
    return square, dark


def lossless(im, path):
    im.save(path, "WEBP", lossless=True, quality=100, method=6, exact=True)
    with Image.open(path) as back:
        assert np.array_equal(np.asarray(back.convert(im.mode)), np.asarray(im)), path


def resized(rgba, size):
    im = Image.fromarray(np.round(rgba).astype(np.uint8), "RGBA").convert("RGBa")
    return np.asarray(im.resize((size, size), Image.LANCZOS).convert("RGBA")).astype(float)


def full_bleed(rgba, dark):
    out = rgba.copy()
    a = out[..., 3:4] / 255
    out[..., :3] = out[..., :3] * a + dark * (1 - a)
    out[..., 3] = 255
    return out


def og_image(lockup, path):
    canvas = Image.new("RGB", (1200, 630), COLORS["cream"])
    logo = Image.fromarray(lockup.astype(np.uint8), "RGB")
    canvas.paste(logo, ((1200 - logo.width) // 2, 92))
    draw = ImageDraw.Draw(canvas)
    bold = ImageFont.truetype(str(FONTS / "DejaVuSans-Bold.ttf"), 44)
    regular = ImageFont.truetype(str(FONTS / "DejaVuSans.ttf"), 26)
    for text, font, y in (("Inspeção visual de frutas com IA", bold, 420), ("Classificação boa/podre por foto · relatórios por setor · foco atual: caju", regular, 492)):
        width = draw.textlength(text, font=font)
        draw.text(((1200 - width) / 2, y), text, font=font, fill=COLORS["ink"])
    canvas.save(path, optimize=True)


def main():
    sheet = np.asarray(Image.open(ROOT / RULES["source"]["file"]).convert("RGB")).astype(float)
    OUT.mkdir(parents=True, exist_ok=True)
    regions = RULES["regions"]
    meta = {"interim": True, "source": RULES["source"], "rules": {"clearSpace": RULES["clearSpace"], "minInkHeightPx": RULES["minInkHeightPx"]}, "colors": COLORS}
    for key, name in (("lockupOnLight", "logo-on-light.png"), ("lockupOnDark", "logo-on-dark.png")):
        crop, box, ink = plate(sheet, regions[key])
        save_png(crop, OUT / name)
        plate_rgb = Image.fromarray(np.round(crop).astype(np.uint8), "RGB")
        web = name.replace(".png", ".webp")
        lossless(plate_rgb, OUT / web)
        meta[key] = {"src": f"brand/{web}", "png": f"brand/{name}", "width": crop.shape[1], "height": crop.shape[0], "inkHeight": ink, "inkBox": box, "inkThreshold": INK, "background": regions[key]["background"], "renditions": []}
        for height in (80, 192):
            if height >= crop.shape[0]:
                continue
            width = round(crop.shape[1] * height / crop.shape[0])
            rendition = name.replace(".png", f"-h{height}.webp")
            lossless(plate_rgb.resize((width, height), Image.LANCZOS), OUT / rendition)
            meta[key]["renditions"].append({"src": f"brand/{rendition}", "height": height})
        if key == "lockupOnLight":
            og_image(crop, OUT / "og-image.png")
    square, dark = icon(sheet, regions["icon"])
    native = square.shape[0]
    save_png(square, OUT / "app-icon.png")
    lossless(Image.fromarray(np.round(square).astype(np.uint8), "RGBA"), OUT / "app-icon.webp")
    lossless(Image.fromarray(np.round(resized(square, 96)).astype(np.uint8), "RGBA"), OUT / "app-icon-96.webp")
    meta["icon"] = {"src": "brand/app-icon.webp", "png": "brand/app-icon.png", "width": native, "height": native, "background": "#%02x%02x%02x" % tuple(int(c) for c in dark), "renditions": [{"src": "brand/app-icon-96.webp", "height": 96}]}
    bleed = full_bleed(square, dark)
    outputs = {"favicon-32.png": (square, 32), "icon-192.png": (square, 192), "icon-512.png": (square, 512), "icon-maskable-512.png": (bleed, 512), "apple-touch-icon.png": (bleed, 180)}
    meta["derived"] = {}
    for name, (source, size) in outputs.items():
        save_png(resized(source, size), OUT / name)
        meta["derived"][name] = {"size": size, "scale": round(size / native, 3), "upscaled": size > native}
    sizes = (16, 32, 48)
    frames = [Image.fromarray(np.round(resized(square, n)).astype(np.uint8), "RGBA") for n in sizes]
    frames[-1].save(OUT / "favicon.ico", sizes=[(n, n) for n in sizes], append_images=frames[:-1])
    meta["derived"]["favicon.ico"] = {"size": list(sizes), "scale": round(max(sizes) / native, 3), "upscaled": False}
    meta["og"] = {"src": "brand/og-image.png", "width": 1200, "height": 630}
    manifest = {
        "name": "FruitCam_ai",
        "short_name": "FruitCam",
        "description": "Inspeção visual de frutas com IA (protótipo; foco atual: caju).",
        "lang": "pt-BR",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": COLORS["cream"],
        "theme_color": COLORS["ink"],
        "icons": [
            {"src": "/static/brand/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/static/brand/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/static/brand/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    (PUBLIC / "manifest.webmanifest").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "frontend" / "src" / "brand.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name in sorted(p.name for p in OUT.iterdir()):
        im = Image.open(OUT / name)
        print(f"{name:24s} {im.size[0]:4d}x{im.size[1]:<4d} {im.mode:5s} {(OUT / name).stat().st_size:7d} B")


if __name__ == "__main__":
    main()
