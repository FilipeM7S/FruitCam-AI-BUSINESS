import datetime
import hashlib
import io
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "media_src" / "commons"
UA = {"User-Agent": "FruitCamAssetTool/1.0 (educational startup prototype; media licensing check)"}
MASTER_MAX = 2560
ALLOWED = re.compile(r"^(CC0|Public domain|CC BY(-SA)? [0-9.]+)$")
FILES = {
    "caju-pacajus": "File:Plantação de caju em Pacajus.jpg",
    "caju-arvore": "File:Cashew apple with nut - Caju.jpg",
    "caju-vermelho": "File:Anacardium occidentale from Margarita island.jpg",
    "castanha": "File:Raw cashew.jpg",
    "melao": "File:Honeydew melon.jpg",
    "guia-bom": "File:Cahew nut fruit 01.jpg",
    "guia-varias": "File:Cajús.jpg",
    "guia-longe": "File:Ripe cashew fruit (483016375).jpg",
    "guia-escuro": "File:Cashew 2.jpg",
}
VIDEOS = {
    "video-batatas": "File:Potatoes Sorting Montana2026 (55252116350).webm",
}


def text(meta, key):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", meta.get(key, {}).get("value", ""))).strip()


def get(url):
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except Exception:
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"download failed: {url}")


def info(title):
    query = urllib.parse.urlencode({"action": "query", "titles": title, "prop": "imageinfo", "iiprop": "url|size|sha1|extmetadata|mediatype", "format": "json", "formatversion": "2"})
    page = json.loads(get(f"https://commons.wikimedia.org/w/api.php?{query}"))["query"]["pages"][0]
    return page["imageinfo"][0]


def public_domain_template(title):
    query = urllib.parse.urlencode({"action": "parse", "page": title, "prop": "templates", "format": "json", "formatversion": "2"})
    names = [t["title"] for t in json.loads(get(f"https://commons.wikimedia.org/w/api.php?{query}"))["parse"]["templates"]]
    found = [n for n in names if re.match(r"^Template:PD-[^/]+$", n) and n != "Template:PD-Layout"]
    assert found, f"{title}: public domain without a PD template"
    return "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(found[0].replace(" ", "_"), safe=":/")


def license_url(title, meta, license_name):
    if text(meta, "LicenseUrl"):
        return text(meta, "LicenseUrl")
    if license_name == "CC0":
        return "https://creativecommons.org/publicdomain/zero/1.0/"
    if license_name == "Public domain":
        return public_domain_template(title)
    return ""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    path = ROOT / "media_src" / "sources.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    sources = {}
    for key, title in {**FILES, **VIDEOS}.items():
        meta_raw = info(title)
        meta = meta_raw["extmetadata"]
        license_name = text(meta, "LicenseShortName")
        assert ALLOWED.match(license_name), f"{title}: license {license_name!r} not allowed"
        assert not text(meta, "Restrictions"), f"{title}: has restrictions {text(meta, 'Restrictions')}"
        video = key in VIDEOS
        master = OUT / (f"{key}.webm" if video else f"{key}.jpg")
        if not master.exists():
            original = get(meta_raw["url"])
            assert hashlib.sha1(original).hexdigest() == meta_raw["sha1"], f"{title}: checksum mismatch"
            if video:
                master.write_bytes(original)
            else:
                im = ImageOps.exif_transpose(Image.open(io.BytesIO(original))).convert("RGB")
                im.thumbnail((MASTER_MAX, MASTER_MAX), Image.LANCZOS)
                im.save(master, "JPEG", quality=92, optimize=True, progressive=True)
            time.sleep(1)
        if video:
            size = (meta_raw["width"], meta_raw["height"])
        else:
            with Image.open(master) as im:
                size = im.size
        sources[key] = {
            "title": title,
            "page": meta_raw["descriptionurl"],
            "file_url": meta_raw["url"],
            "author": text(meta, "Artist"),
            "credit": text(meta, "Credit"),
            "license": license_name,
            "license_url": license_url(title, meta, license_name),
            "attribution_required": text(meta, "AttributionRequired") != "false",
            "date": text(meta, "DateTimeOriginal") or text(meta, "DateTime"),
            "original_size": [meta_raw["width"], meta_raw["height"]],
            "original_sha1": meta_raw["sha1"],
            "master": f"media_src/commons/{master.name}",
            "master_size": list(size),
            "master_note": "Arquivo original, sem alteração." if video else f"Original reduzido para no máximo {MASTER_MAX} px no maior lado, sem metadados EXIF.",
            "retrieved": previous.get(key, {}).get("retrieved") or datetime.date.today().isoformat(),
            "kind": "video" if video else "image",
            "duration_s": meta_raw.get("duration"),
        }
        print(f"{key:14s} {license_name:14s} {sources[key]['author'][:40]:40s} {size}")
    (ROOT / "media_src" / "sources.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
