import json
import os
import threading
from pathlib import Path

NL = b"\n"
COMPACT_BYTES = 1_000_000


class Spool:
    def __init__(self, folder, name="passages", sync=True):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / f"{name}.jsonl"
        self.mark = self.folder / f"{name}.offset"
        self.sync = sync
        self.lock = threading.Lock()
        self.corrupt = 0
        self.path.touch(exist_ok=True)
        self.offset = self.read_mark()
        if self.offset > self.path.stat().st_size:
            self.offset = 0
            self.write_mark(0)
        self.seal()

    def read_mark(self):
        try:
            return int(self.mark.read_text(encoding="ascii").strip() or 0)
        except (OSError, ValueError):
            return 0

    def write_mark(self, offset):
        tmp = self.mark.with_name(self.mark.name + ".tmp")
        tmp.write_text(str(offset), encoding="ascii")
        os.replace(tmp, self.mark)

    def seal(self):
        with self.lock, self.path.open("rb+") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            if size == 0:
                return
            handle.seek(size - 1)
            if handle.read(1) != NL:
                handle.write(NL)

    def append(self, records):
        if not records:
            return
        data = b"".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + NL for r in records)
        with self.lock, self.path.open("ab") as handle:
            handle.write(data)
            handle.flush()
            if self.sync:
                os.fsync(handle.fileno())

    def pending(self, limit=500):
        with self.lock, self.path.open("rb") as handle:
            handle.seek(self.offset)
            records, offset = [], self.offset
            for line in handle:
                if not line.endswith(NL) or len(records) >= limit:
                    break
                offset += len(line)
                try:
                    records.append(json.loads(line))
                except ValueError:
                    self.corrupt += 1
            return records, offset

    def commit(self, offset):
        with self.lock:
            size = self.path.stat().st_size
            if offset >= size and size >= COMPACT_BYTES:
                self.path.write_bytes(b"")
                offset = 0
            self.offset = offset
            self.write_mark(offset)

    def backlog_bytes(self):
        try:
            return max(self.path.stat().st_size - self.offset, 0)
        except OSError:
            return 0
