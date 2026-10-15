import hashlib
import io
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg
from PIL import Image

import build_legal

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "media_src"
PUBLIC = ROOT / "frontend" / "public"
OUT = PUBLIC / "media"
FRONT = ROOT / "frontend" / "src"
FORMATS = {
    "avif": ("AVIF", "avif", {"quality": 52, "speed": 6}),
    "webp": ("WEBP", "webp", {"quality": 74, "method": 6}),
    "jpeg": ("JPEG", "jpg", {"quality": 80, "optimize": True, "progressive": True}),
}
BUDGET = {"avif": 160_000, "webp": 220_000, "jpeg": 300_000}
FLOOR = {"avif": 30, "webp": 50, "jpeg": 55}


CLIPS = {
    "demo": ("demo-video", "Vídeo de demonstração e capturas de tela do app (aparece na interface gravada)"),
    "primeira-analise": ("primeira-analise-video", "Vídeo da primeira análise, no Histórico vazio (aparece na interface gravada)"),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()[:10]


def crop(im, box):
    if not box:
        return im
    w, h = im.size
    return im.crop((round(box[0] * w), round(box[1] * h), round(box[2] * w), round(box[3] * h)))


def encode(im, fmt, start=None):
    name, _, options = FORMATS[fmt]
    quality = (start or {}).get(fmt, options["quality"])
    while True:
        buf = io.BytesIO()
        im.save(buf, name, **{**options, "quality": quality})
        if buf.tell() <= BUDGET[fmt] or quality <= FLOOR[fmt]:
            return buf.getvalue()
        quality -= 4


def derivatives(variant, master, box, widths, quality=None):
    im = crop(Image.open(master).convert("RGB"), box)
    usable = sorted({min(w, im.width) for w in widths})
    sources = {fmt: [] for fmt in FORMATS}
    files = []
    size = None
    for w in usable:
        h = round(im.height * w / im.width)
        scaled = im.resize((w, h), Image.LANCZOS)
        size = (w, h)
        for fmt in FORMATS:
            data = encode(scaled, fmt, quality)
            rel = f"media/{variant}.{w}.{digest(data)}.{FORMATS[fmt][1]}"
            (PUBLIC / rel).write_bytes(data)
            sources[fmt].append([w, rel])
            files.append(rel)
    return sources, files, size


def copy_hashed(src, stem):
    data = src.read_bytes()
    rel = f"media/video/{stem}.{digest(data)}{src.suffix}"
    (PUBLIC / rel).write_bytes(data)
    return rel


def clip(master, start, duration, crop, width, out_stem, work):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    vf = (f"crop={crop}," if crop else "") + f"scale={width}:-2:flags=lanczos,fps=25,format=yuv420p"
    files = {}
    for ext, args in (("webm", ["-c:v", "libvpx-vp9", "-crf", "48", "-b:v", "0", "-row-mt", "1", "-deadline", "good", "-cpu-used", "2"]), ("mp4", ["-c:v", "libx264", "-crf", "34", "-preset", "veryslow", "-movflags", "+faststart"])):
        out = work / f"{out_stem}.{ext}"
        trim = ["-ss", str(start), "-t", str(duration)] if start is not None else []
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", *trim, "-i", str(master), "-vf", vf, *args, "-an", "-map_metadata", "-1", str(out)], check=True)
        files[ext] = out
    poster = work / f"{out_stem}-poster.png"
    middle = (start or 0) + (duration or 1) / 2
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-ss", str(middle), "-i", str(master), "-vf", (f"crop={crop}," if crop else "") + f"scale={width}:-2:flags=lanczos", "-frames:v", "1", str(poster)], check=True)
    return files, poster


def main():
    sources = json.loads((SRC / "sources.json").read_text(encoding="utf-8"))
    catalog = json.loads((SRC / "catalog.json").read_text(encoding="utf-8"))
    figures = json.loads((FRONT / "figures.json").read_text(encoding="utf-8")) if (FRONT / "figures.json").exists() else {"items": {}}
    for old in sorted(OUT.rglob("*"), reverse=True) if OUT.exists() else []:
        if old.is_file():
            old.unlink()
    (OUT / "video").mkdir(parents=True, exist_ok=True)
    items, by_asset = {}, {}
    for variant, v in catalog["variants"].items():
        meta = sources[v["asset"]]
        srcset, files, size = derivatives(variant, ROOT / meta["master"], v["crop"], v["widths"], v.get("quality"))
        items[variant] = {
            "asset": v["asset"],
            "alt": v["alt"],
            "illustrative": True,
            "width": size[0],
            "height": size[1],
            "sources": srcset,
            "fallback": srcset["jpeg"][len(srcset["jpeg"]) // 2][1],
        }
        entry = by_asset.setdefault(v["asset"], {"used_in": [], "files": [], "cropped": False})
        entry["used_in"].append(v["usedIn"])
        entry["files"] += files
        entry["cropped"] |= bool(v["crop"])
    owned = {}
    for name, (asset_id, used) in CLIPS.items():
        clip_meta = SRC / "video" / f"{name}.json"
        if not clip_meta.exists():
            continue
        rec = json.loads(clip_meta.read_text(encoding="utf-8"))
        poster_set, poster_files, poster_size = derivatives(f"{name}-poster", SRC / "video" / f"{name}-poster.png", None, [480, 960, 1280])
        items[f"{name}-poster"] = {"asset": asset_id, "alt": rec["posterAlt"], "illustrative": False, "width": poster_size[0], "height": poster_size[1], "sources": poster_set, "fallback": poster_set["jpeg"][-1][1]}
        video_files = {key: copy_hashed(SRC / "video" / f"{name}.{ext}", name) for key, ext in (("webm", "webm"), ("mp4", "mp4"), ("captions", "vtt"))}
        items[name] = {"kind": "video", "asset": asset_id, "poster": f"{name}-poster", "posterSrc": poster_set["webp"][-1][1], "width": rec["width"], "height": rec["height"], "alt": rec["alt"], "caption": rec["caption"], "transcript": rec["transcript"], **video_files}
        for asset in rec.get("contains", []):
            by_asset.setdefault(asset, {"used_in": [], "files": [], "cropped": False})["used_in"].append(used)
        owned[asset_id] = {"files": [*video_files.values(), *poster_files]}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for bg, v in catalog.get("backgrounds", {}).items():
            if "own" in v:
                own = ROOT / v["own"]
                files = {"webm": own.with_suffix(".webm"), "mp4": own.with_suffix(".mp4")}
                poster = own.with_name(own.name + "-poster.png")
                meta, asset = None, "belt-sim"
            else:
                asset = v["asset"]
                meta = sources[asset]
                files, poster = clip(ROOT / meta["master"], v["start"], v["duration"], v.get("crop"), v["width"], bg, work)
            poster_set, poster_files, size = derivatives(f"{bg}-poster", poster, None, [640, v["width"]])
            video_files = {key: copy_hashed(path, bg) for key, path in files.items()}
            illustrative = meta is not None
            items[f"{bg}-poster"] = {"asset": asset, "alt": v["alt"], "illustrative": illustrative, "width": size[0], "height": size[1], "sources": poster_set, "fallback": poster_set["jpeg"][-1][1]}
            ordered = sorted(video_files.items(), key=lambda kv: (PUBLIC / kv[1]).stat().st_size)
            items[bg] = {"kind": "background", "asset": asset, "illustrative": illustrative, "alt": v["alt"], "poster": f"{bg}-poster", "posterSrc": poster_set["webp"][-1][1], "width": size[0], "height": size[1], "sources": [{"src": rel, "type": f"video/{key}"} for key, rel in ordered], **video_files}
            if meta:
                entry = by_asset.setdefault(asset, {"used_in": [], "files": [], "cropped": False, "clip": None})
                entry["used_in"].append(v["usedIn"])
                entry["files"] += [*video_files.values(), *poster_files]
                entry["clip"] = {k: v[k] for k in ("start", "duration", "width")}
            else:
                owned["belt-sim"] = {"files": [*video_files.values(), *poster_files]}
    for fig in figures["items"].values():
        for asset in fig.get("assets", []):
            by_asset.setdefault(asset, {"used_in": [], "files": [], "cropped": False})["used_in"].append(f"Figura {fig['number']} (Como funciona e kit do Summit)")
    usage = {asset: {"used_in": use["used_in"], "cropped": use["cropped"], "clip": use.get("clip"), "files": use["files"]} for asset, use in by_asset.items() if asset in sources}
    usage["brand"] = {"files": [*sorted(f"brand/{p.name}" for p in (PUBLIC / "brand").iterdir()), "manifest.webmanifest"]}
    usage.update(owned)
    if figures["items"]:
        usage["figures"] = {"files": sorted(f"figures/{p.name}" for p in (PUBLIC / "figures").iterdir() if p.is_file())}
    registered = {e["id"] for section in ("media", "own") for e in build_legal.registry()[section]}
    missing = sorted(set(usage) - registered)
    assert not missing, f"sem registro em legal/registry.json: {missing}"
    (FRONT / "media.json").write_text(json.dumps({"items": items}, ensure_ascii=False, indent=1) + chr(10), encoding="utf-8")
    build_legal.write(build_legal.USAGE, build_legal.dump(usage))
    for path, text in build_legal.outputs().items():
        build_legal.write(path, text)
    total = 0
    for variant, item in items.items():
        if item.get("kind") in ("video", "background"):
            continue
        largest = {fmt: (PUBLIC / item["sources"][fmt][-1][1]).stat().st_size for fmt in FORMATS}
        total += sum((PUBLIC / rel).stat().st_size for fmt in FORMATS for _, rel in item["sources"][fmt])
        print(f"{variant:16s} {item['width']:5d}x{item['height']:<5d} largest avif {largest['avif']:7d} B  webp {largest['webp']:7d} B  jpeg {largest['jpeg']:7d} B")
    print(f"images: {len(items)} variants, {total} B on disk across all formats and widths")


if __name__ == "__main__":
    main()
