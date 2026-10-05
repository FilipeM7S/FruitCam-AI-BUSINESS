import time

import cv2


class CameraSource:
    def __init__(self, spec, reconnect_s=2.0):
        self.spec = int(spec) if str(spec).isdigit() else spec
        self.live = not (isinstance(self.spec, str) and not self.spec.startswith(("rtsp://", "rtsps://", "http://", "https://")))
        self.reconnect_s = reconnect_s
        self.capture = None
        self.started = time.monotonic()
        self.index = 0
        self.fps = None
        self.open()

    def open(self):
        self.capture = cv2.VideoCapture(self.spec)
        fps = self.capture.get(cv2.CAP_PROP_FPS)
        self.fps = fps if fps and fps > 1 else 25.0

    def read(self):
        ok, frame = self.capture.read()
        while not ok:
            if not self.live:
                return None, None
            self.capture.release()
            time.sleep(self.reconnect_s)
            self.open()
            ok, frame = self.capture.read()
        self.index += 1
        t = time.monotonic() - self.started if self.live else (self.index - 1) / self.fps
        return t, frame

    def close(self):
        if self.capture is not None:
            self.capture.release()
