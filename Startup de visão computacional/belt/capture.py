import threading
import time

import cv2

OPEN_TIMEOUT_MS = 5000
READ_TIMEOUT_MS = 5000


def open_capture(spec):
    if isinstance(spec, str):
        try:
            capture = cv2.VideoCapture(spec, cv2.CAP_FFMPEG, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, OPEN_TIMEOUT_MS, cv2.CAP_PROP_READ_TIMEOUT_MSEC, READ_TIMEOUT_MS])
        except (cv2.error, TypeError, AttributeError):
            capture = cv2.VideoCapture(spec)
    else:
        capture = cv2.VideoCapture(spec)
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return capture


def is_live(spec):
    return isinstance(spec, int) or str(spec).isdigit() or str(spec).startswith(("rtsp://", "rtsps://", "http://", "https://"))


class LatestFrame:
    def __init__(self, spec, opener=open_capture, backoff=(0.5, 30.0)):
        self.spec = int(spec) if str(spec).isdigit() else spec
        self.opener = opener
        self.backoff = backoff
        self.cond = threading.Condition()
        self.halt = threading.Event()
        self.thread = None
        self.frame = None
        self.seq = 0
        self.taken = 0
        self.grabbed = 0
        self.dropped = 0
        self.reconnects = 0
        self.failures = 0
        self.state = "connecting"
        self.started = time.monotonic()
        self.stamp = (0.0, 0.0)

    def start(self):
        self.thread = threading.Thread(target=self.run, name="fruitcam-grabber", daemon=True)
        self.thread.start()
        return self

    def run(self):
        capture, delay, connected = None, self.backoff[0], False
        while not self.halt.is_set():
            if capture is None:
                capture = self.opener(self.spec)
                if not capture.isOpened():
                    capture.release()
                    capture = None
                    self.failures += 1
                    self.state = "reconnecting" if connected else "connecting"
                    self.halt.wait(delay)
                    delay = min(delay * 2, self.backoff[1])
                    continue
            ok, frame = capture.read()
            if not ok or frame is None:
                capture.release()
                capture = None
                self.failures += 1
                self.reconnects += 1
                self.state = "reconnecting"
                self.halt.wait(delay)
                delay = min(delay * 2, self.backoff[1])
                continue
            delay, connected = self.backoff[0], True
            with self.cond:
                self.frame = frame
                self.seq += 1
                self.grabbed += 1
                self.stamp = (time.monotonic() - self.started, time.time())
                self.state = "running"
                self.cond.notify_all()
        if capture is not None:
            capture.release()

    def read(self, timeout=1.0):
        with self.cond:
            if not self.cond.wait_for(lambda: self.seq != self.taken, timeout):
                return None
            self.dropped += self.seq - self.taken - 1
            self.taken = self.seq
            return self.stamp[0], self.frame, self.stamp[1]

    def age(self):
        return time.monotonic() - self.started - self.stamp[0] if self.seq else None

    def close(self, timeout=8.0):
        self.halt.set()
        if self.thread is not None:
            self.thread.join(timeout)
