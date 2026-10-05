import argparse
import datetime
import hashlib
import json
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META = ROOT / "scripts" / "datasets.json"
EXTERNAL = ROOT / "data" / "external"
UA = {"User-Agent": "FruitCamDatasetFetch/1.0 (startup prototype; licence-checked download)"}
CHUNK = 1 << 20


def digest(path, algo):
    h = hashlib.new(algo)
    with path.open("rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


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
    hashes = {"md5": hashlib.md5(), "sha256": hashlib.sha256()}
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
    for algo in ("md5", "sha256"):
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
        hashes = {algo: digest(target, algo) for algo in ("md5", "sha256")}
        for algo in ("md5", "sha256"):
            if algo in spec and hashes[algo] != spec[algo]:
                raise SystemExit(f"{target}: {algo} does not match the published value; delete it and run again")
        got = 0
    else:
        print(f"  downloading {spec['name']} ({spec['size'] / 1e6:.0f} MB) from {spec['url']}", flush=True)
        got, hashes = download(spec["url"], target, spec)
    published = {algo: spec[algo] for algo in ("md5", "sha256") if algo in spec}
    marker.write_text(json.dumps({"stamp": stamp_of(target), "size": spec["size"], "hashes": hashes, "published": published, "verified_on": datetime.date.today().isoformat()}, indent=1) + "\n", encoding="utf-8")
    return got, hashes


def extract(raw, spec, out):
    marker = out / ".extracted.json"
    source = raw / spec["name"]
    if marker.exists() and json.loads(marker.read_text(encoding="utf-8")).get("from") == {**stamp_of(source), "name": spec["name"]}:
        return False
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as z:
        z.extractall(out)
        names = [n for n in z.namelist() if not n.endswith("/")]
    for inner in sorted(out.rglob("*.zip")):
        target = inner.with_suffix("")
        if not target.exists():
            with zipfile.ZipFile(inner) as z:
                z.extractall(target)
    marker.write_text(json.dumps({"from": {**stamp_of(source), "name": spec["name"]}, "files": len(names)}, indent=1) + "\n", encoding="utf-8")
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
        f"- Authors: {ds['authors']}" + (f" ({ds['institution']})" if ds["institution"] else ""),
        f"- Setting: {ds['setting']}",
        f"- Fruit: {ds['fruit']}",
        f"- Licence: [{ds['licence']}]({ds['licence_url']})",
        f"- Licence as written on the source: {ds['licence_as_written']}",
        f"- Commercial use: {ds['commercial_use']}",
        "",
        "## Required attribution",
        "",
        ds["attribution"],
        "",
        "## Citation",
        "",
        ds["citation"],
        "",
        "## Files",
        "",
    ]
    for spec in ds["files"]:
        h = hashes[spec["name"]]
        published = ", ".join(f"{a} {spec[a]}" for a in ("md5", "sha256") if a in spec)
        lines += [f"- `raw/{spec['name']}` ({spec['size']:,} B) from {spec['url']}", f"  - published: {published}", f"  - computed: md5 {h['md5']}, sha256 {h['sha256']}", f"  - matches published: {all(h[a] == spec[a] for a in ('md5', 'sha256') if a in spec)}"]
    for spec in ds.get("not_downloaded", []):
        lines += [f"- Not downloaded: `{spec['name']}` ({spec['size']:,} B, published sha256 {spec['sha256']}). {spec['reason']}"]
    lines += extra
    lines += ["", f"Recorded by `scripts/fetch_datasets.py` on {datetime.date.today().isoformat()}.", ""]
    return "\n".join(lines)


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
        home = EXTERNAL / ds["id"]
        raw = home / "raw"
        raw.mkdir(parents=True, exist_ok=True)
        hashes, got, extra = {}, 0, []
        for spec in ds["files"]:
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
        changed = write_if_changed(home / "SOURCE.md", source_md(ds, hashes, extra))
        total += got
        print(f"{ds['id']:16s} {'downloaded ' + format(got, ',') + ' B' if got else 'already present and verified, nothing downloaded'}{'; SOURCE.md written' if changed else ''}", flush=True)
    print(f"total downloaded: {total:,} B")


if __name__ == "__main__":
    main()
