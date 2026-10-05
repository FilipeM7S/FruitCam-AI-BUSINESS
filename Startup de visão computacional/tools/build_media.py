import hashlib
import io
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg
from urllib.parse import unquote

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "media_src"
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


def credit(asset, meta, catalog):
    kind = "Vídeo" if meta.get("kind") == "video" else "Foto"
    terms = "domínio público" if meta["license"].lower() == "public domain" else meta["license"]
    return f"{kind}: {catalog['assets'][asset]['creditName']} · {terms} · Wikimedia Commons"


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


def attribution(meta, catalog, asset):
    title = meta["title"].removeprefix("File:").rsplit(".", 1)[0]
    terms = "dedicada ao domínio público (CC0)" if meta["license"] == "CC0" else "em domínio público (Public domain)" if meta["license"].lower() == "public domain" else meta["license"]
    return f"“{title}”, por {catalog['assets'][asset]['creditName']} ({meta['author']}), {terms}, via Wikimedia Commons: {unquote(meta['page'])}"


def main():
    sources = json.loads((SRC / "sources.json").read_text(encoding="utf-8"))
    catalog = json.loads((SRC / "catalog.json").read_text(encoding="utf-8"))
    figures = json.loads((FRONT / "figures.json").read_text(encoding="utf-8")) if (FRONT / "figures.json").exists() else {"items": {}}
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "video").mkdir(parents=True)
    items, by_asset = {}, {}
    for variant, v in catalog["variants"].items():
        meta = sources[v["asset"]]
        srcset, files, size = derivatives(variant, ROOT / meta["master"], v["crop"], v["widths"], v.get("quality"))
        items[variant] = {
            "asset": v["asset"],
            "alt": v["alt"],
            "illustrative": True,
            "credit": credit(v["asset"], meta, catalog),
            "width": size[0],
            "height": size[1],
            "sources": srcset,
            "fallback": srcset["jpeg"][len(srcset["jpeg"]) // 2][1],
        }
        entry = by_asset.setdefault(v["asset"], {"used_in": [], "files": [], "cropped": False})
        entry["used_in"].append(v["usedIn"])
        entry["files"] += files
        entry["cropped"] |= bool(v["crop"])
    first_party = []
    demo_meta = SRC / "video" / "demo.json"
    if demo_meta.exists():
        demo = json.loads(demo_meta.read_text(encoding="utf-8"))
        poster_set, poster_files, poster_size = derivatives("demo-poster", SRC / "video" / "demo-poster.png", None, [480, 960, 1280])
        items["demo-poster"] = {"asset": "demo-video", "alt": demo["posterAlt"], "illustrative": False, "credit": demo["credit"], "width": poster_size[0], "height": poster_size[1], "sources": poster_set, "fallback": poster_set["jpeg"][-1][1]}
        video_files = {key: copy_hashed(SRC / "video" / f"demo.{ext}", "demo") for key, ext in (("webm", "webm"), ("mp4", "mp4"), ("captions", "vtt"))}
        items["demo"] = {"kind": "video", "asset": "demo-video", "poster": "demo-poster", "posterSrc": poster_set["webp"][-1][1], "width": demo["width"], "height": demo["height"], "alt": demo["alt"], "caption": demo["caption"], "transcript": demo["transcript"], **video_files}
        for asset in demo.get("contains", []):
            by_asset.setdefault(asset, {"used_in": [], "files": [], "cropped": False})["used_in"].append("Vídeo de demonstração e capturas de tela do app (aparece na interface gravada)")
        first_party.append({"id": "demo-video", "title": "Vídeo de demonstração do app", "license": "Material próprio da FruitCam; as fotos de terceiros visíveis na interface mantêm suas licenças, listadas acima", "source": "Gravação de tela do app real em execução (tools/record_demo.py), com dados sintéticos", "note": demo["credit"], "files": [*video_files.values(), *poster_files]})
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
            text = credit(asset, meta, catalog) if meta else "Simulação própria da FruitCam (tools/record_belt.py)"
            items[f"{bg}-poster"] = {"asset": asset, "alt": v["alt"], "illustrative": illustrative, "credit": text, "width": size[0], "height": size[1], "sources": poster_set, "fallback": poster_set["jpeg"][-1][1]}
            ordered = sorted(video_files.items(), key=lambda kv: (PUBLIC / kv[1]).stat().st_size)
            items[bg] = {"kind": "background", "asset": asset, "illustrative": illustrative, "credit": text, "alt": v["alt"], "poster": f"{bg}-poster", "posterSrc": poster_set["webp"][-1][1], "width": size[0], "height": size[1], "sources": [{"src": rel, "type": f"video/{key}"} for key, rel in ordered], **video_files}
            if meta:
                entry = by_asset.setdefault(asset, {"used_in": [], "files": [], "cropped": False, "clip": None})
                entry["used_in"].append(v["usedIn"])
                entry["files"] += [*video_files.values(), *poster_files]
                entry["clip"] = v
            else:
                first_party.append({"id": "belt-sim", "title": "Vídeo de simulação da esteira", "license": "Material próprio da FruitCam", "source": "Gerado por tools/record_belt.py: esteira e frutas desenhadas por código, processadas pelo mesmo pipeline da câmera", "note": "Rótulos vêm da simulação, não do modelo de IA.", "files": [*video_files.values(), *poster_files]})
    for fig in figures["items"].values():
        for asset in fig.get("assets", []):
            by_asset.setdefault(asset, {"used_in": [], "files": [], "cropped": False})["used_in"].append(f"Figura {fig['number']} (Como funciona e kit do Summit)")
    third_party = []
    for asset, meta in sources.items():
        use = by_asset.get(asset)
        if not use:
            continue
        if use.get("clip"):
            v = use["clip"]
            mods = f"Trecho de {v['duration']:g} s a partir de {str(v['start']).replace('.', ',')} s, recortado para excluir mãos e rostos, reduzido para {v['width']} px de largura, sem áudio; convertido para WebM (VP9) e MP4 (H.264); quadro central como pôster em AVIF, WebP e JPEG."
        else:
            mods = "Original reduzido para no máximo 2560 px e sem metadados" + ("; recortado" if use["cropped"] else "") + "; convertido para AVIF, WebP e JPEG em várias larguras."
        if "SA" in meta["license"]:
            mods += " Os derivados seguem a mesma licença (CC BY-SA)."
        third_party.append({
            "id": asset,
            "title": catalog["assets"][asset]["title"],
            "commons_title": meta["title"],
            "author": meta["author"],
            "license": meta["license"],
            "license_url": meta["license_url"],
            "source_url": meta["page"],
            "file_url": meta["file_url"],
            "date": meta["date"],
            "retrieved": meta["retrieved"],
            "attribution_text": attribution(meta, catalog, asset),
            "modifications": mods,
            "used_in": use["used_in"],
            "files": use["files"],
            "illustrative": True,
        })
    brand_files = sorted(f"brand/{p.name}" for p in (PUBLIC / "brand").iterdir())
    first_party.insert(0, {"id": "brand", "title": "Logotipo FruitCam_ai (provisório)", "license": "Marca da FruitCam; uso restrito", "source": "brand/source/logo-kit-sheet.png (imagem do kit enviada pela equipe)", "note": "Recortes exatos, sem alterar cores nem proporções, da imagem do kit enviada pela equipe; serão substituídos pelos arquivos vetoriais originais.", "files": [*brand_files, "manifest.webmanifest"]})
    if figures["items"]:
        figure_files = sorted(f"figures/{p.name}" for p in (PUBLIC / "figures").iterdir() if p.is_file())
        first_party.append({"id": "figures", "title": "Figuras científicas", "license": "Material próprio da FruitCam", "source": "Geradas por figures/make_figures.py a partir de dados sintéticos e de medições reais", "note": "A Figura 2 contém a foto “caju-vermelho” (CC0).", "files": figure_files})
    (FRONT / "media.json").write_text(json.dumps({"items": items}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    meta = json.loads((ROOT / "scripts" / "datasets.json").read_text(encoding="utf-8"))
    datasets = [{k: d[k] for k in ("id", "title", "authors", "institution", "version", "doi", "page", "licence", "licence_url", "licence_as_written", "commercial_use", "attribution", "setting", "fruit")} for d in meta["datasets"]]
    (FRONT / "licenses.json").write_text(json.dumps({"third_party": third_party, "first_party": first_party, "datasets": datasets}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
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
