import io
import json
import struct
import time
import urllib.request
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

UA = {"User-Agent": "FruitCamDatasetFetch/1.0 (startup prototype; licence-checked download)"}
LOCAL_HEADER = 30
SLACK = 512


def fetch(url, start, end, attempts=8):
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={**UA, "Range": f"bytes={start}-{end - 1}"})
            with urllib.request.urlopen(request, timeout=120) as response:
                if response.status != 206:
                    raise OSError(f"server ignored the range request (status {response.status})")
                data = response.read()
            if len(data) != end - start:
                raise OSError(f"short read: {len(data)} of {end - start} bytes")
            return data
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(min(30, 2 * (attempt + 1)))


class RangeFile(io.RawIOBase):
    def __init__(self, url, size, block=1 << 20):
        self.url = url
        self.size = size
        self.block = block
        self.position = 0
        self.start = 0
        self.buffer = b""
        self.requests = 0
        self.received = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=io.SEEK_SET):
        self.position = offset if whence == io.SEEK_SET else self.position + offset if whence == io.SEEK_CUR else self.size + offset
        return self.position

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.position
        n = max(0, min(n, self.size - self.position))
        if n == 0:
            return b""
        inside = self.start <= self.position and self.position + n <= self.start + len(self.buffer)
        if not inside:
            end = min(self.size, self.position + max(n, self.block))
            self.buffer = fetch(self.url, self.position, end)
            self.start = self.position
            self.requests += 1
            self.received += len(self.buffer)
        at = self.position - self.start
        self.position += n
        return self.buffer[at:at + n]


def index(url, size):
    handle = RangeFile(url, size)
    with zipfile.ZipFile(handle) as archive:
        entries = [{"name": i.filename, "offset": i.header_offset, "stored": i.compress_size, "size": i.file_size, "crc": i.CRC, "method": i.compress_type} for i in archive.infolist() if not i.is_dir()]
    return entries, {"requests": handle.requests, "bytes": handle.received}


def unpack(raw, entry):
    signature, _, _, _, _, _, _, _, _, name_len, extra_len = struct.unpack("<IHHHHHIIIHH", raw[:LOCAL_HEADER])
    if signature != 0x04034B50:
        raise ValueError(f"{entry['name']}: not a local file header")
    begin = LOCAL_HEADER + name_len + extra_len
    packed = raw[begin:begin + entry["stored"]]
    if len(packed) != entry["stored"]:
        return None
    if entry["method"] == zipfile.ZIP_STORED:
        data = packed
    elif entry["method"] == zipfile.ZIP_DEFLATED:
        data = zlib.decompress(packed, -15)
    else:
        raise ValueError(f"{entry['name']}: unsupported compression {entry['method']}")
    if len(data) != entry["size"] or zlib.crc32(data) != entry["crc"]:
        raise ValueError(f"{entry['name']}: size or CRC-32 does not match the archive index")
    return data


def reach(entry):
    return entry["offset"] + LOCAL_HEADER + len(entry["name"].encode("utf-8")) + SLACK + entry["stored"]


def member(url, entry, total):
    raw = fetch(url, entry["offset"], min(total, reach(entry)))
    data = unpack(raw, entry)
    if data is None:
        raise ValueError(f"{entry['name']}: local header longer than expected")
    return data


def batches(entries, gap=1 << 16, limit=24 << 20):
    group = []
    for entry in sorted(entries, key=lambda e: e["offset"]):
        if group and (entry["offset"] - reach(group[-1]) > gap or reach(entry) - group[0]["offset"] > limit):
            yield group
            group = []
        group.append(entry)
    if group:
        yield group


def present(target, entry):
    return target.exists() and target.stat().st_size == entry["size"] and zlib.crc32(target.read_bytes()) == entry["crc"]


def mirror(url, total, entries, folder, workers=4, progress=None):
    folder = Path(folder)
    wanted = [e for e in entries if not present(folder / e["name"], e)]
    done = {"files": 0, "bytes": 0, "requests": 0, "skipped": len(entries) - len(wanted)}
    started = time.time()

    def one(group):
        start, end = group[0]["offset"], min(total, reach(group[-1]))
        raw = fetch(url, start, end)
        for entry in group:
            data = unpack(raw[entry["offset"] - start:], entry)
            if data is None:
                data = member(url, entry, total)
            target = folder / entry["name"]
            target.parent.mkdir(parents=True, exist_ok=True)
            part = target.with_name(target.name + ".part")
            part.write_bytes(data)
            part.replace(target)
        return len(group), end - start

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for files, size in pool.map(one, list(batches(wanted))):
            done["files"] += files
            done["bytes"] += size
            done["requests"] += 1
            if progress and done["requests"] % progress == 0:
                print(f"  {done['files']} of {len(wanted)} files, {done['bytes'] / 1e6:.0f} MB in {time.time() - started:.0f} s", flush=True)
    done["seconds"] = round(time.time() - started)
    return done


def save_index(path, entries, source):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"source": source, "entries": entries}, indent=0) + chr(10), encoding="utf-8")


def load_index(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))["entries"]
