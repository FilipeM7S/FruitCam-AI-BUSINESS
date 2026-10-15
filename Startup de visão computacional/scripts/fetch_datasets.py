import argparse
import datetime
import hashlib
import json
import os
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META = ROOT / "scripts" / "datasets.json"
EXTERNAL = ROOT / "data" / "external"
STORE = Path(os.environ.get("FRUITCAM_DATA_STORE") or Path.home() / "FruitCamData")
UA = {"User-Agent": "FruitCamDatasetFetch/1.0 (startup prototype; licence-checked download)"}
CHUNK = 1 << 20
ALGOS = ("md5", "sha1", "sha256")


def digest(path, algo):
    h = hashlib.new(algo)
    with path.open("rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def home_of(ds):
    return (STORE if ds.get("store") == "outside" else EXTERNAL) / ds["id"]


def stamp_of(path):
    st = path.stat()
    return {"size": st.st_size, "mtime_ns": st.st_mtime_ns}


def verified(path, spec, marker):
    if not path.exists() or not marker.exists():
        return False
    record = json.loads(marker.read_text(encoding="utf-8"))
    return record.get("stamp") == stamp_of(path) and record.get("size") == spec["size"]


def download(url, target, spec, attempts=20):
    part = target.with_name(target.name + ".part")
    hashes = {algo: hashlib.new(algo) for algo in ALGOS}
    done = 0
    if part.exists():
        with part.open("rb") as f:
            for block in iter(lambda: f.read(CHUNK), b""):
                for h in hashes.values():
                    h.update(block)
                done += len(block)
        print(f"  resuming {target.name} at {done / 1e6:.0f} MB", flush=True)
    last = time.time()
    for attempt in range(attempts):
        if done >= spec["size"]:
            break
        try:
            headers = {**UA, "Range": f"bytes={done}-"} if done else UA
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as r, part.open("ab") as out:
                if done and r.status != 206:
                    raise SystemExit(f"{target.name}: server ignored the resume request")
                for block in iter(lambda: r.read(CHUNK), b""):
                    out.write(block)
                    for h in hashes.values():
                        h.update(block)
                    done += len(block)
                    if time.time() - last > 30:
                        print(f"  {target.name}: {done / 1e6:.0f} of {spec['size'] / 1e6:.0f} MB", flush=True)
                        last = time.time()
        except (OSError, ConnectionError) as e:
            print(f"  {target.name}: connection lost at {done / 1e6:.0f} MB ({e.__class__.__name__}); retry {attempt + 1}", flush=True)
            time.sleep(min(60, 5 * (attempt + 1)))
    if done != spec["size"]:
        part.unlink()
        raise SystemExit(f"{target.name}: got {done} bytes, expected {spec['size']}")
    for algo in ALGOS:
        if algo in spec and hashes[algo].hexdigest() != spec[algo]:
            part.unlink()
            raise SystemExit(f"{target.name}: {algo} mismatch")
    part.replace(target)
    return done, {algo: h.hexdigest() for algo, h in hashes.items()}


def fetch_file(ds, spec, raw):
    target = raw / spec["name"]
    marker = raw / f"{spec['name']}.verified.json"
    if verified(target, spec, marker):
        return 0, json.loads(marker.read_text(encoding="utf-8"))["hashes"]
    if target.exists() and target.stat().st_size == spec["size"]:
        hashes = {algo: digest(target, algo) for algo in ALGOS}
        for algo in ALGOS:
            if algo in spec and hashes[algo] != spec[algo]:
                raise SystemExit(f"{target}: {algo} does not match the published value; delete it and run again")
        got = 0
    else:
        print(f"  downloading {spec['name']} ({spec['size'] / 1e6:.0f} MB) from {spec['url']}", flush=True)
        got, hashes = download(spec["url"], target, spec)
    published = {algo: spec[algo] for algo in ALGOS if algo in spec}
    marker.write_text(json.dumps({"stamp": stamp_of(target), "size": spec["size"], "hashes": hashes, "published": published, "verified_on": datetime.date.today().isoformat()}, indent=1) + "\n", encoding="utf-8")
    return got, hashes


def extract(raw, spec, out):
    if not spec["name"].endswith(".zip") or spec.get("extract") is False:
        return False
    marker = out / ".extracted.json"
    source = raw / spec["name"]
    if marker.exists() and json.loads(marker.read_text(encoding="utf-8")).get("from") == {**stamp_of(source), "name": spec["name"]}:
        return False
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        wanted = spec.get("only")
        members = [n for n in names if not wanted or n.lower().endswith(tuple(wanted))]
        z.extractall(out, members)
    for inner in sorted(out.rglob("*.zip")):
        target = inner.with_suffix("")
        if not target.exists():
            with zipfile.ZipFile(inner) as z:
                z.extractall(target)
    marker.write_text(json.dumps({"from": {**stamp_of(source), "name": spec["name"]}, "files": len(members), "skipped": len(names) - len(members)}, indent=1) + "\n", encoding="utf-8")
    return True


def local_digest(ds):
    loc = ds["local"]
    rows = []
    counts = {}
    for key in ("images", "labels"):
        files = sorted(p for p in (ROOT / loc[key]).iterdir() if p.is_file())
        counts[key] = len(files)
        rows += [f"{loc[key]}/{p.name}:{digest(p, 'sha256')}" for p in files]
    return counts, hashlib.sha256("\n".join(rows).encode()).hexdigest()


def source_md(ds, hashes, extra):
    lines = [
        f"# {ds['title']}",
        "",
        f"- Dataset id in this project: `{ds['id']}`",
        f"- Page: {ds['page']}",
        f"- DOI: {('https://doi.org/' + ds['doi']) if ds['doi'] else 'none'}",
        f"- Version: {ds['version']}",
        f"- Setting: {ds['setting']}",
        f"- Fruit: {ds['fruit']}",
        f"- Licence, authors and required attribution: [LICENSES.md](../../../LICENSES.md), section 3, entry `{ds['id']}`",
        "",
        "## Files",
        "",
    ]
    for spec in ds["files"]:
        if spec.get("partial"):
            lines += [f"- `{spec['name']}` ({spec['size']:,} B) at {spec['url']}", f"  - published: sha256 {spec.get('sha256', 'none')}", "  - not downloaded in full; see the section about partial download below"]
            continue
        h = hashes[spec["name"]]
        published = ", ".join(f"{a} {spec[a]}" for a in ALGOS if a in spec)
        computed = ", ".join(f"{a} {h[a]}" for a in ALGOS if a in h and (a != "sha1" or "sha1" in spec))
        lines += [f"- `raw/{spec['name']}` ({spec['size']:,} B) from {spec['url']}", f"  - published: {published}", f"  - computed: {computed}", f"  - matches published: {all(h[a] == spec[a] for a in ALGOS if a in spec)}"]
        if "page" in spec:
            lines += [f"  - source page: {spec['page']}"]
    for spec in ds.get("not_downloaded", []):
        lines += [f"- Not downloaded: `{spec['name']}` ({spec['size']:,} B, published sha256 {spec['sha256']}). {spec['reason']}"]
    lines += extra
    lines += ["", f"Recorded by `scripts/fetch_datasets.py` on {datetime.date.today().isoformat()}.", ""]
    return "\n".join(lines)


def partial_lines(intake):
    lines = ["", "## Partial download", "", f"- Method: {intake['method']}.", "- Tool: `python tools/fetch_cashew_drone.py` (it repeats the same selection and downloads only what is missing)."]
    for name, info in intake["archives"].items():
        lines += [f"- `{name}`: {info['files_present_and_matching_crc']:,} of {info['files_in_archive']:,} files present ({info['photos_present']:,} of {info['photos_in_archive']:,} photos, all {info['label_files']:,} label files), {info['bytes_present']:,} B."]
        if "selection_rule" in info:
            lines += [f"  - Photos chosen: {info['selection_rule']}."]
    return lines


def write_if_changed(path, text):
    old = path.read_text(encoding="utf-8") if path.exists() else None
    body = lambda s: "\n".join(l for l in s.splitlines() if not l.startswith("Recorded by"))
    if old is not None and body(old) == body(text):
        return False
    path.write_text(text, encoding="utf-8")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args()
    meta = json.loads(META.read_text(encoding="utf-8"))
    total = 0
    for ds in meta["datasets"]:
        if args.only and ds["id"] not in args.only:
            continue
        home = home_of(ds)
        raw = home / "raw"
        raw.mkdir(parents=True, exist_ok=True)
        hashes, got, extra = {}, 0, []
        for spec in ds["files"]:
            if spec.get("partial"):
                continue
            n, h = fetch_file(ds, spec, raw)
            hashes[spec["name"]] = h
            got += n
            if extract(raw, spec, home / "extracted" / Path(spec["name"]).stem):
                print(f"  extracted {spec['name']}", flush=True)
        if "local" in ds:
            counts, combined = local_digest(ds)
            ok = counts == {"images": ds["local"]["expected_images"], "labels": ds["local"]["expected_label_files"]}
            if not ok:
                raise SystemExit(f"{ds['id']}: expected {ds['local']['expected_images']} images and {ds['local']['expected_label_files']} label files, found {counts}")
            extra = ["", "## Local copy", "", f"- {ds['local']['note']}", f"- Files in the project: `{ds['local']['images']}/` ({counts['images']} images) and `{ds['local']['labels']}/` ({counts['labels']} label files)", f"- Content digest (sha256 over the sorted list of `path:sha256` lines of both folders): {combined}"]
        card = EXTERNAL / ds["id"] / "SOURCE.md"
        card.parent.mkdir(parents=True, exist_ok=True)
        intake = home / "intake.json"
        if intake.exists():
            extra = [*extra, *partial_lines(json.loads(intake.read_text(encoding="utf-8")))]
        if ds.get("store") == "outside":
            extra = [*extra, "", "## Where the files are", "", "- This set is large, so the archives and the extracted files are kept outside the project folder, in the directory named by `FRUITCAM_DATA_STORE` (default: `FruitCamData` in the user's home folder), under `" + ds["id"] + "/`. Only this card is in the project."]
        changed = write_if_changed(card, source_md(ds, hashes, extra))
        total += got
        note = "; large archives fetched in part by tools/fetch_cashew_drone.py" if any(spec.get("partial") for spec in ds["files"]) else ""
        print(f"{ds['id']:16s} {'downloaded ' + format(got, ',') + ' B' if got else 'already present and verified, nothing downloaded'}{note}{'; SOURCE.md written' if changed else ''}", flush=True)
    print(f"total downloaded: {total:,} B")


if __name__ == "__main__":
    main()
