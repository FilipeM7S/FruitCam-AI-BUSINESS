import hashlib
import io
import platform
import unicodedata
from functools import lru_cache
from importlib import metadata
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
import numpy as np
from django.conf import settings
from PIL import Image
from reportlab import rl_config
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import BaseDocTemplate, CondPageBreak, Flowable, Frame, KeepTogether, NextPageTemplate, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.platypus.tableofcontents import TableOfContents

from analytics import fruit_analytics as FA
from belt import stats as BS
from belt.stats import wilson

from . import certificate_charts as C
from .certificate_data import MAX_LINE_WINDOWS
from .certificate_text import AI_ERRORS, DECLARATIONS, T, bucket_label, ci, clock, date_br, datetime_br, dec, fill, minutes_label, name, num, pct, period_label, pp, prob, pvalue, signed_pct

VERSION = "2.0"
PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
W = PAGE_W - 2 * MARGIN
BAND = 100 * mm
BRAND = settings.BASE_DIR / "frontend" / "public" / "brand"
BRAND_FONTS = settings.BASE_DIR / "assets" / "brand" / "fonts"
MPL_FONTS = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
INK = colors.HexColor("#14231e")
CREAM = colors.HexColor("#f5f1e6")
RED = colors.HexColor("#d9432a")
TEAL = colors.HexColor("#3fab94")
TEAL_LIGHT = colors.HexColor("#8fd3bf")
TAN = colors.HexColor("#c9a47a")
TAN_DARK = colors.HexColor("#8a6a45")
MUTED = colors.HexColor("#5b6b63")
RULE = colors.HexColor("#e2dccd")
ZEBRA = colors.HexColor("#f8f5ee")
WARN = colors.HexColor("#b07400")
WARN_BG = colors.HexColor("#fdf3dc")
INFO_BG = colors.HexColor("#eef5f1")
DANGER_BG = colors.HexColor("#fbece8")
rl_config.useA85 = 0

FONT_CHOICES = {
    "Display": (("Fraunces-Display.ttf", BRAND_FONTS), ("DejaVuSerif-Bold.ttf", MPL_FONTS)),
    "Serif": (("Fraunces-Text.ttf", BRAND_FONTS), ("DejaVuSerif.ttf", MPL_FONTS)),
    "SerifItalic": (("Fraunces-TextItalic.ttf", BRAND_FONTS), ("DejaVuSerif-Italic.ttf", MPL_FONTS)),
    "Sans": (("Inter-Regular.ttf", BRAND_FONTS), ("DejaVuSans.ttf", MPL_FONTS)),
    "SansMedium": (("Inter-Medium.ttf", BRAND_FONTS), ("DejaVuSans.ttf", MPL_FONTS)),
    "SansSemi": (("Inter-SemiBold.ttf", BRAND_FONTS), ("DejaVuSans-Bold.ttf", MPL_FONTS)),
    "SansBold": (("Inter-Bold.ttf", BRAND_FONTS), ("DejaVuSans-Bold.ttf", MPL_FONTS)),
    "Mono": (("JetBrainsMono-Regular.ttf", BRAND_FONTS), ("DejaVuSansMono.ttf", MPL_FONTS)),
    "MonoBold": (("JetBrainsMono-SemiBold.ttf", BRAND_FONTS), ("DejaVuSansMono-Bold.ttf", MPL_FONTS)),
}
BRANDED = all((options[0][1] / options[0][0]).exists() for options in FONT_CHOICES.values())
for alias, options in FONT_CHOICES.items():
    file, folder = next((f, d) for f, d in options if (d / f).exists())
    pdfmetrics.registerFont(TTFont(alias, str(folder / file)))
pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="SansSemi", italic="Sans", boldItalic="SansSemi")
pdfmetrics.registerFontFamily("Serif", normal="Serif", bold="Display", italic="SerifItalic", boldItalic="Display")
pdfmetrics.registerFontFamily("Mono", normal="Mono", bold="MonoBold", italic="Mono", boldItalic="MonoBold")


def style(key, **kw):
    return ParagraphStyle(key, **{"fontName": "Sans", "fontSize": 8.6, "leading": 12.6, "textColor": INK, **kw})


S = {
    "body": style("body", alignment=TA_JUSTIFY, spaceAfter=4),
    "lead": style("lead", fontSize=9.3, leading=13.6, textColor=MUTED, spaceAfter=6),
    "small": style("small", fontSize=7.2, leading=10, textColor=MUTED, spaceAfter=3),
    "how": style("how", fontSize=7.2, leading=10, textColor=MUTED, spaceBefore=1, spaceAfter=6),
    "kicker": style("kicker", fontName="SansSemi", fontSize=6.6, leading=8.6, textColor=TAN_DARK),
    "num": style("num", fontName="Display", fontSize=40, leading=40, textColor=RED),
    "title": style("title", fontName="Display", fontSize=21, leading=25, textColor=INK, spaceBefore=1),
    "h2": style("h2", fontName="SansSemi", fontSize=11.4, leading=15, spaceBefore=12, spaceAfter=2),
    "h3": style("h3", fontName="SansSemi", fontSize=8.7, leading=12, spaceBefore=8, spaceAfter=2),
    "fig": style("fig", fontName="SansSemi", fontSize=8.2, leading=11.2, spaceBefore=6, spaceAfter=2),
    "th": style("th", fontName="SansSemi", fontSize=6.7, leading=8.6, textColor=CREAM),
    "kv_k": style("kv_k", fontName="SansSemi", fontSize=6.4, leading=8.4, textColor=TAN_DARK),
    "kv_v": style("kv_v", fontSize=8, leading=10.6),
    "mono": style("mono", fontName="Mono", fontSize=6.9, leading=9.2),
    "bullet": style("bullet", leftIndent=12, bulletIndent=2, spaceAfter=3, alignment=TA_LEFT, bulletFontName="Sans", bulletFontSize=5.6, bulletColor=RED),
    "note": style("note", fontSize=7.6, leading=10.6),
    "ai_left": style("ai_left", fontName="Display", fontSize=13.5, leading=17),
    "ai_sub": style("ai_sub", fontSize=7.5, leading=10.4, textColor=MUTED, spaceBefore=2),
    "attest": style("attest", fontName="SerifItalic", fontSize=10.3, leading=15.4, alignment=TA_CENTER),
    "toc_title": style("toc_title", fontName="Display", fontSize=20, leading=24, spaceAfter=10),
    "tile_label": style("tile_label", fontName="SansSemi", fontSize=6.2, leading=8, textColor=TAN_DARK),
    "tile_value": style("tile_value", fontName="SansSemi", fontSize=17, leading=20),
    "tile_sub": style("tile_sub", fontSize=6.6, leading=8.6, textColor=MUTED),
    "cell": style("cell", fontSize=7, leading=9),
    "cell_r": style("cell_r", fontSize=7, leading=9, alignment=TA_RIGHT),
}
TOC_STYLES = [
    style("toc0", fontName="SansSemi", fontSize=9.2, leading=12, spaceBefore=3.5),
    style("toc1", fontSize=7.8, leading=9.6, leftIndent=16, textColor=MUTED),
]


def esc(x):
    return escape(str(x))


def P(text, key="body"):
    return Paragraph(text, S[key])


def ascii_text(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def fingerprint_layers(fp):
    b = bytes.fromhex(fp)
    return [(6 + b[i] % 12, 2 + b[i + 8] % 5, b[i + 16] / 255 * 2 * np.pi) for i in range(3)]


def has_glyphs(font, text):
    face = pdfmetrics.getFont(font).face
    return all(ord(ch) in face.charToGlyph for ch in text)


def draft(c):
    return getattr(getattr(c, "_doctemplate", None), "draft", False)


def draw_wave(c, x0, x1, y, amp, period, phase, step=1.4 * mm):
    if draft(c):
        return
    xs = np.arange(x0, x1 + step, step)
    ys = y + amp * np.sin(2 * np.pi * (xs - x0) / period + phase)
    path = c.beginPath()
    path.moveTo(xs[0], ys[0])
    for x, yv in zip(xs[1:], ys[1:]):
        path.lineTo(x, yv)
    c.drawPath(path, stroke=1, fill=0)


def draw_guilloche(c, x0, x1, y, height, lines, color, alpha, period, phase=0.0, width=0.32):
    c.saveState()
    c.setStrokeColor(color)
    c.setStrokeAlpha(alpha)
    c.setLineWidth(width)
    for j in range(lines):
        t = 2 * np.pi * j / lines
        draw_wave(c, x0, x1, y, height / 2 * (0.55 + 0.45 * np.cos(t)), period, phase + t)
    c.restoreState()


def draw_rosette(c, r_in, r_out, fp, palette, copies=14, steps=320):
    if draft(c):
        return
    theta = np.linspace(0, 2 * np.pi, steps + 1)
    for k, ((n, m, phase), color) in enumerate(zip(fingerprint_layers(fp), palette)):
        lo = r_in + (r_out - r_in) * 0.12 * k
        hi = r_out - (r_out - r_in) * 0.16 * k
        mid, amp = (lo + hi) / 2, (hi - lo) / 2
        c.setStrokeColor(color)
        for j in range(copies):
            rot = 2 * np.pi * j / (copies * n)
            rho = mid + amp * np.sin(n * (theta + rot) + phase) * (0.62 + 0.38 * np.cos(m * theta))
            path = c.beginPath()
            path.moveTo(rho[0] * np.cos(theta[0]), rho[0] * np.sin(theta[0]))
            for r, t in zip(rho[1:], theta[1:]):
                path.lineTo(r * np.cos(t), r * np.sin(t))
            c.drawPath(path, stroke=1, fill=0)


@lru_cache(maxsize=32)
def micro_line(text, width, size):
    widths = np.cumsum([pdfmetrics.stringWidth(ch, "Sans", size) for ch in text])
    repeats = int(width // widths[-1]) + 1
    total = np.concatenate([widths + k * widths[-1] for k in range(repeats + 1)])
    return (text * (repeats + 1))[: int(np.searchsorted(total, width, side="right"))]


def draw_microtext(c, x, y, width, text, color, size=2.4):
    c.saveState()
    c.setFont("Sans", size)
    c.setFillColor(color)
    c.drawString(x, y, micro_line(text, round(width, 2), size))
    c.restoreState()


def draw_circular_text(c, text, radius, font, size, color):
    c.setFont(font, size)
    c.setFillColor(color)
    step = 360 / len(text)
    for i, ch in enumerate(text):
        c.saveState()
        c.rotate(90 - i * step)
        c.translate(radius, 0)
        c.rotate(-90)
        c.drawCentredString(0, 0, ch)
        c.restoreState()


class Anchor(Flowable):
    def __init__(self, level, text, key, tab=None):
        super().__init__()
        self.level, self.text, self.key, self.tab = level, text, key, tab

    def wrap(self, aw, ah):
        return 0, 0

    def draw(self):
        pass


class Wave(Flowable):
    def __init__(self, color=TEAL, height=3.2 * mm, lines=5, alpha=0.75, period=26 * mm):
        super().__init__()
        self.color, self.h, self.lines, self.alpha, self.period = color, height, lines, alpha, period

    def wrap(self, aw, ah):
        self.aw = aw
        return aw, self.h + 2

    def draw(self):
        draw_guilloche(self.canv, 0, self.aw, self.h / 2 + 1, self.h, self.lines, self.color, self.alpha, self.period, width=0.35)


class PNG(Flowable):
    def __init__(self, png, width, height, align="CENTER"):
        super().__init__()
        self.reader = ImageReader(Image.open(io.BytesIO(png)).convert("RGB"))
        self.w, self.h = width, height
        self.hAlign = align

    def wrap(self, aw, ah):
        return self.w, self.h

    def draw(self):
        if not draft(self.canv):
            self.canv.drawImage(self.reader, 0, 0, self.w, self.h)


class Seal(Flowable):
    def __init__(self, size, fp, number):
        super().__init__()
        self.size, self.fp, self.number = size, fp, number
        self.icon = ImageReader(str(BRAND / "app-icon.png"))

    def wrap(self, aw, ah):
        return self.size, self.size

    def draw(self):
        c = self.canv
        r = self.size / 2
        c.saveState()
        c.translate(r, r)
        c.setFillColor(CREAM)
        c.setStrokeColor(INK)
        c.setLineWidth(1.2)
        c.circle(0, 0, r - 0.8, stroke=1, fill=1)
        ring = min(4.6 * mm, r * 0.2)
        c.setLineWidth(0.5)
        c.setStrokeColor(TAN)
        c.circle(0, 0, r - ring)
        c.setLineWidth(0.22)
        c.setStrokeAlpha(0.85)
        draw_rosette(c, r * 0.3, r - ring - 0.9 * mm, self.fp, (TEAL, RED, TAN_DARK), copies=12 if self.size < 50 * mm else 16)
        c.setStrokeAlpha(1)
        text = f"FRUITCAM_AI · {self.number} · CERTIFICADO DIGITAL · "
        draw_circular_text(c, text, r - ring * 0.72, "SansSemi", max(4.6, min(6.4, self.size / mm * 0.15)), INK)
        disc = r * 0.3
        c.setFillColor(CREAM)
        c.setStrokeColor(TAN)
        c.setLineWidth(0.5)
        c.circle(0, 0, disc, stroke=1, fill=1)
        side = disc * 1.5
        c.drawImage(self.icon, -side / 2, -side / 2, side, side, mask="auto")
        c.restoreState()


class QR(Flowable):
    def __init__(self, payload, size):
        super().__init__()
        self.size = size
        widget = QrCodeWidget(payload, barLevel="M", barFillColor=INK, barStrokeColor=INK)
        x0, y0, x1, y1 = widget.getBounds()
        self.drawing = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
        self.drawing.add(widget)

    def wrap(self, aw, ah):
        return self.size, self.size

    def draw(self):
        if not draft(self.canv):
            renderPDF.draw(self.drawing, self.canv, 0, 0)


class Tile(Flowable):
    def __init__(self, label, value, sub, accent, width, height=23 * mm):
        super().__init__()
        self.label, self.value, self.sub, self.accent, self.w, self.h = label, value, sub, accent, width, height

    def wrap(self, aw, ah):
        return self.w, self.h

    def draw(self):
        c = self.canv
        c.setFillColor(colors.white)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        c.roundRect(0, 0, self.w, self.h, 2.4 * mm, stroke=1, fill=1)
        c.setFillColor(self.accent)
        c.roundRect(0, self.h - 1.6 * mm, self.w, 1.6 * mm, 0.8 * mm, stroke=0, fill=1)
        pad = 3 * mm
        for text, key, y in ((self.label.upper(), "tile_label", self.h - 6.4 * mm), (self.value, "tile_value", self.h - 14.4 * mm), (self.sub, "tile_sub", 2.4 * mm)):
            p = Paragraph(esc(text), S[key])
            p.wrap(self.w - 2 * pad, self.h)
            p.drawOn(c, pad, y)


class Spark(Flowable):
    def __init__(self, values, width=30 * mm, height=6.5 * mm):
        super().__init__()
        self.values, self.w, self.h = values, width, height

    def wrap(self, aw, ah):
        return self.w, self.h

    def draw(self):
        v = np.array([np.nan if x is None else x for x in self.values], float)
        if not np.isfinite(v).any():
            return
        c = self.canv
        hi = max(0.05, np.nanmax(v) * 1.1)
        xs = np.linspace(0, self.w, len(v)) if len(v) > 1 else np.array([self.w / 2])
        ys = 1 + v / hi * (self.h - 2)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.4)
        c.line(0, 1, self.w, 1)
        c.setStrokeColor(INK)
        c.setLineWidth(0.7)
        path, pen = c.beginPath(), False
        for x, y in zip(xs, ys):
            if np.isfinite(y):
                path.lineTo(x, y) if pen else path.moveTo(x, y)
                pen = True
            else:
                pen = False
        c.drawPath(path, stroke=1, fill=0)
        last = np.flatnonzero(np.isfinite(v))[-1]
        c.setFillColor(RED)
        c.circle(xs[last], ys[last], 0.8, stroke=0, fill=1)


class Alert(Flowable):
    def __init__(self, size=9 * mm):
        super().__init__()
        self.size = size

    def wrap(self, aw, ah):
        return self.size, self.size

    def draw(self):
        c, r = self.canv, self.size / 2
        c.setFillColor(RED)
        c.circle(r, r, r, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("SansBold", self.size * 0.62)
        c.drawCentredString(r, r - self.size * 0.22, "!")


class Bottom(Flowable):
    def __init__(self, inner):
        super().__init__()
        self.inner = inner

    def wrap(self, aw, ah):
        self.iw, self.ih = self.inner.wrap(aw, ah)
        return aw, max(self.ih, ah - 1)

    def draw(self):
        self.inner.drawOn(self.canv, 0, 0)


def box(content, bg, border, bar=False, pad=7, width=W):
    t = Table([[content]], colWidths=[width])
    st = [("BACKGROUND", (0, 0), (-1, -1), bg), ("LEFTPADDING", (0, 0), (-1, -1), pad + (2 if bar else 0)), ("RIGHTPADDING", (0, 0), (-1, -1), pad), ("TOPPADDING", (0, 0), (-1, -1), pad * 0.8), ("BOTTOMPADDING", (0, 0), (-1, -1), pad * 0.9)]
    st.append(("LINEBEFORE", (0, 0), (0, -1), 2.6, border) if bar else ("BOX", (0, 0), (-1, -1), 1, border))
    t.setStyle(TableStyle(st))
    return t


def note(text, tone="warn"):
    bg, border = {"warn": (WARN_BG, WARN), "info": (INFO_BG, TEAL), "danger": (DANGER_BG, RED)}[tone]
    t = box([P(text, "note")], bg, border, bar=True, pad=5)
    t.spaceBefore, t.spaceAfter = 2, 4
    return t


def ai_box(width=W, sub=True):
    text = [P(esc(AI_ERRORS), "ai_left")] + ([P(esc(T["ai_sub"]), "ai_sub")] if sub else [])
    t = Table([[Alert(), text]], colWidths=[13 * mm, width - 13 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DANGER_BG), ("BOX", (0, 0), (-1, -1), 1, RED), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def bullets(items):
    return [Paragraph(text, S["bullet"], bulletText="◆") for text in items]


def how(items):
    return P(f"<b>{esc(T['how_read'])}:</b> " + " · ".join(esc(i) for i in items), "how")


def table(head, rows, widths, right=(), size=7):
    widths = [w * W for w in widths]
    fits = [max(4, int(w / (size * 0.56))) for w in widths]

    def cell(v, i):
        if isinstance(v, Flowable):
            return v
        s = str(v)
        return Paragraph(esc(s), S["cell_r"] if i in right else S["cell"]) if len(s) > fits[i] else s

    th_r = ParagraphStyle("th_r", parent=S["th"], alignment=TA_RIGHT)
    data = [[Paragraph(esc(h), th_r if i in right else S["th"]) for i, h in enumerate(head)]] + [[cell(v, i) for i, v in enumerate(r)] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    st = [
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("LINEBELOW", (0, 0), (-1, 0), 1.4, RED),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONT", (0, 1), (-1, -1), "Sans", size),
        ("TEXTCOLOR", (0, 1), (-1, -1), INK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 2.3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.7),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    st += [("ALIGN", (c, 1), (c, -1), "RIGHT") for c in right]
    t.setStyle(TableStyle(st))
    return t


def kv(rows, label=0.34, width=W):
    data = [[Paragraph(esc(k).upper(), S["kv_k"]), v if isinstance(v, Flowable) else Paragraph(esc(v), S["kv_v"])] for k, v in rows]
    t = Table(data, colWidths=[label * width, (1 - label) * width], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 2.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def grid(rows, width, cols=2):
    cells = [[Paragraph(esc(k).upper(), S["kv_k"]), Paragraph(esc(v), S["kv_v"])] for k, v in rows]
    data = [cells[i:i + cols] + [""] * (cols - len(cells[i:i + cols])) for i in range(0, len(cells), cols)]
    t = Table(data, colWidths=[width / cols] * cols, hAlign="CENTER")
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEABOVE", (0, 0), (-1, 0), 0.8, INK),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, TAN),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.6),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def clipped(limit):
    m, cut = limit
    return [note(esc(fill(T["badges"]["clipped"], m=signed_pct(m, 0) if m < 50 else num(m))), "info")] if cut else []


@lru_cache(maxsize=4)
def file_sha256(path, mtime):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def model_hash():
    path = settings.MODEL_PATH
    return file_sha256(str(path), path.stat().st_mtime) if path.exists() else None


def versions():
    out = [("Python", platform.python_version())]
    for pkg in ("Django", "numpy", "pandas", "scipy", "matplotlib", "reportlab", "pillow"):
        try:
            out.append((pkg, metadata.version(pkg)))
        except metadata.PackageNotFoundError:
            pass
    return out


class Doc(BaseDocTemplate):
    def __init__(self, buf, meta):
        self.meta = meta
        self.tab = None
        self.section_title = ""
        super().__init__(buf, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=24 * mm, bottomMargin=20 * mm, title=f"{T['title']} {meta['number']}", author=T["brand"], subject=T["subtitle"], creator=f"{T['brand']} certificado v{VERSION}", producer=T["brand"], keywords=T["keywords"], lang="pt-BR")
        cover = Frame(21 * mm, 15 * mm, PAGE_W - 42 * mm, PAGE_H - BAND - 21 * mm, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="cover")
        body = Frame(MARGIN, 20 * mm, W, PAGE_H - 44 * mm, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="body")
        self.addPageTemplates([
            PageTemplate("cover", [cover], onPage=self.draw_cover, onPageEnd=self.draw_watermark),
            PageTemplate("body", [body], onPageEnd=self.draw_body),
        ])
        self.icon = ImageReader(str(BRAND / "app-icon.png"))
        self.logo = ImageReader(str(BRAND / "logo-on-dark.png"))

    def beforeDocument(self):
        self.tab, self.section_title = None, ""

    def afterFlowable(self, flowable):
        if isinstance(flowable, Anchor):
            self.canv.bookmarkPage(flowable.key)
            self.canv.addOutlineEntry(flowable.text, flowable.key, level=flowable.level, closed=flowable.level > 0)
            self.notify("TOCEntry", (flowable.level, flowable.text, self.page, flowable.key))
            if flowable.tab:
                self.tab = flowable.tab
                self.section_title = flowable.text

    def draw_cover(self, c, doc):
        m = self.meta
        c.saveState()
        c.setFillColor(CREAM)
        c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
        c.setFillColor(INK)
        c.rect(0, PAGE_H - BAND, PAGE_W, BAND, stroke=0, fill=1)
        draw_guilloche(c, 0, PAGE_W, PAGE_H - BAND + 13 * mm, 16 * mm, 16, TEAL, 0.32, 58 * mm)
        draw_guilloche(c, 0, PAGE_W, PAGE_H - BAND + 13 * mm, 10 * mm, 12, TAN, 0.3, 37 * mm, phase=1.1)
        lw, lh = self.logo.getSize()
        w = 58 * mm
        c.drawImage(self.logo, (PAGE_W - w) / 2, PAGE_H - 12 * mm - w * lh / lw, w, w * lh / lw)
        kicker = T["kicker"]
        c.setFont("SansSemi", 8.4)
        c.setFillColor(TAN)
        width = pdfmetrics.stringWidth(kicker, "SansSemi", 8.4) + 3.4 * (len(kicker) - 1)
        c.drawString((PAGE_W - width) / 2, PAGE_H - 45 * mm, kicker, charSpace=3.4)
        size = min(30, (PAGE_W - 44 * mm) / pdfmetrics.stringWidth(T["title"], "Display", 1))
        c.setFont("Display", size)
        c.setFillColor(CREAM)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 57 * mm, T["title"])
        c.setFont("Sans", 10)
        c.setFillColor(TEAL_LIGHT)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 64.5 * mm, T["subtitle"])
        number = fill(T["number"], n=m["number"])
        c.setFont("Mono", 10)
        nw = pdfmetrics.stringWidth(number, "Mono", 10) + 9 * mm
        c.setStrokeColor(TAN)
        c.setLineWidth(0.7)
        c.roundRect((PAGE_W - nw) / 2, PAGE_H - 76 * mm, nw, 7.4 * mm, 3.7 * mm, stroke=1, fill=0)
        c.setFillColor(CREAM)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 73.4 * mm, number)
        c.setStrokeColor(RED)
        c.setLineWidth(1.1)
        draw_wave(c, 0, PAGE_W, PAGE_H - BAND, 1.1 * mm, 14 * mm, 0)
        c.setStrokeColor(TAN)
        c.setLineWidth(0.8)
        c.rect(7 * mm, 7 * mm, PAGE_W - 14 * mm, PAGE_H - 14 * mm)
        c.setStrokeColor(INK)
        c.setLineWidth(0.35)
        c.rect(8.6 * mm, 8.6 * mm, PAGE_W - 17.2 * mm, PAGE_H - BAND - 8.6 * mm - 2.2 * mm)
        for x, y in ((7, 7), (PAGE_W / mm - 7, 7), (7, PAGE_H / mm - 7), (PAGE_W / mm - 7, PAGE_H / mm - 7)):
            c.saveState()
            c.translate(x * mm, y * mm)
            c.rotate(45)
            c.setFillColor(RED)
            c.rect(-1.3 * mm, -1.3 * mm, 2.6 * mm, 2.6 * mm, stroke=0, fill=1)
            c.restoreState()
        micro = f"FRUITCAM_AI · CERTIFICADO DE ANÁLISE ESTATÍSTICA · {m['number']} · SHA-256 {m['fingerprint']} · "
        draw_microtext(c, 10.5 * mm, 10.2 * mm, PAGE_W - 21 * mm, micro, TAN_DARK)
        draw_microtext(c, 10.5 * mm, PAGE_H - 9.8 * mm, PAGE_W - 21 * mm, micro, TAN)
        c.restoreState()

    def draw_body(self, c, doc):
        m = self.meta
        c.saveState()
        band = 11 * mm
        c.setFillColor(INK)
        c.rect(0, PAGE_H - band, PAGE_W, band, stroke=0, fill=1)
        c.setStrokeColor(RED)
        c.setLineWidth(1.2)
        c.line(0, PAGE_H - band, PAGE_W, PAGE_H - band)
        c.drawImage(self.icon, MARGIN, PAGE_H - band + 1.7 * mm, 7.6 * mm, 7.6 * mm, mask="auto")
        c.setFillColor(CREAM)
        c.setFont("SansSemi", 8.6)
        c.drawString(MARGIN + 10 * mm, PAGE_H - 6.9 * mm, T["brand"])
        c.setFillColor(TAN)
        c.setFont("Sans", 7.4)
        c.drawString(MARGIN + 10 * mm + pdfmetrics.stringWidth(T["brand"], "SansSemi", 8.6) + 2.4 * mm, PAGE_H - 6.9 * mm, T["header"])
        c.setFillColor(CREAM)
        c.setFont("Mono", 7.4)
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 6.9 * mm, fill(T["number"], n=m["number"]))
        draw_microtext(c, MARGIN, PAGE_H - band - 2.6 * mm, W, f"FRUITCAM_AI · {m['number']} · SHA-256 {m['fingerprint']} · ", TAN_DARK, 2.2)
        if self.section_title:
            c.setFont("Sans", 6.8)
            c.setFillColor(MUTED)
            c.drawRightString(PAGE_W - MARGIN, PAGE_H - band - 6.6 * mm, self.section_title)
        if self.tab:
            tabs = [t for t in m["tabs"] if t]
            index = tabs.index(self.tab) if self.tab in tabs else 0
            y = PAGE_H - 30 * mm - index * 14.5 * mm
            c.setFillColor(INK)
            c.roundRect(PAGE_W - 7.2 * mm, y - 12 * mm, 10 * mm, 12 * mm, 1.8 * mm, stroke=0, fill=1)
            c.setFillColor(RED)
            c.rect(PAGE_W - 7.2 * mm, y - 12 * mm, 0.9 * mm, 12 * mm, stroke=0, fill=1)
            c.setFillColor(CREAM)
            c.setFont("SansBold", 8.4)
            c.drawCentredString(PAGE_W - 3.4 * mm, y - 7.3 * mm, self.tab)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.line(MARGIN, 15 * mm, PAGE_W - MARGIN, 15 * mm)
        c.saveState()
        c.translate(MARGIN + 0.9 * mm, 11 * mm)
        c.rotate(45)
        c.setFillColor(RED)
        c.rect(-0.9 * mm, -0.9 * mm, 1.8 * mm, 1.8 * mm, stroke=0, fill=1)
        c.restoreState()
        c.setFillColor(INK)
        c.setFont("SansSemi", 7.4)
        c.drawString(MARGIN + 3.2 * mm, 10.2 * mm, AI_ERRORS)
        c.setFillColor(MUTED)
        c.setFont("Mono", 5.8)
        c.drawString(MARGIN, 6.2 * mm, f"{fill(T['footer_hash'], h=m['fingerprint'][:16] + '…')} · {T['issued_at']} {datetime_br(m['issued'])}")
        c.restoreState()
        self.draw_watermark(c, doc)

    def draw_watermark(self, c, doc):
        if not self.meta["demo"]:
            return
        c.saveState()
        c.setFillColor(RED)
        c.setFillAlpha(0.07)
        c.translate(PAGE_W / 2, PAGE_H / 2)
        c.rotate(52)
        c.setFont("SansBold", 44)
        c.drawCentredString(0, 6 * mm, T["watermark"])
        c.setFont("SansSemi", 17)
        c.drawCentredString(0, -6 * mm, T["watermark_sub"])
        c.restoreState()


def numbered_canvas(skip=1):
    class NumberedCanvas(rl_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.states = []

        def showPage(self):
            self.states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self.states)
            for i, state in enumerate(self.states, 1):
                self.__dict__.update(state)
                if i > skip:
                    self.setFont("Mono", 7.2)
                    self.setFillColor(INK)
                    self.drawRightString(PAGE_W - MARGIN, 10.2 * mm, fill(T["page"], i=i, n=total))
                super().showPage()
            super().save()

    return NumberedCanvas


class Builder:
    def __init__(self, data, meta):
        self.d, self.meta = data, meta
        self.dash, self.line, self.sc = data["dashboard"], data["line"], data["scope"]
        self.story = []
        self.n_section = 0
        self.n_key = 0
        self.n_figure = 0

    def add(self, *flowables):
        self.story.extend(flowables)

    def key(self):
        self.n_key += 1
        return f"s{self.n_key}"

    def opener(self, text, numbered=True, tab=None, kicker=None):
        self.add(PageBreak())
        if numbered:
            self.n_section += 1
            tab = str(self.n_section)
            label, kicker, big, title = f"{self.n_section}. {text}", fill(T["section"], n=f"{self.n_section:02d}"), f"{self.n_section:02d}", text
        else:
            label, big = text, tab
            kicker, title = (text.split(": ", 1)[0].upper(), text.split(": ", 1)[1]) if ": " in text else (kicker or "", text)
        self.meta["tabs"].append(tab)
        head = ([P(esc(kicker), "kicker")] if kicker else []) + [P(esc(title), "title")]
        glyph = esc(big) if has_glyphs("Display", big) else f'<font name="SansSemi">{esc(big)}</font>'
        t = Table([[P(glyph, "num"), head]], colWidths=[24 * mm, W - 24 * mm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        self.add(Anchor(0, label, self.key(), tab), t, Wave(), Spacer(1, 3 * mm))

    def h2(self, text):
        self.add(CondPageBreak(45 * mm), Anchor(1, text, self.key()), P(esc(text), "h2"))

    def h3(self, text):
        return [CondPageBreak(30 * mm), P(esc(text), "h3")]

    def ok(self, key):
        return self.dash[key]["status"] == "ok"

    def chart(self, c, title=None, notes=()):
        self.n_figure += 1
        label = f'<font name="MonoBold" color="#1f6f5f">{esc(fill(T["figure"], n=f"{self.n_figure:02d}")).upper()}</font>'
        head = P(f"{label}&nbsp;&nbsp;{esc(title)}" if title else label, "fig")
        return KeepTogether([head, *notes, PNG(c.png, c.width * mm, c.height * mm), Spacer(1, 3)])

    def build(self):
        self.meta["tabs"] = []
        self.cover()
        self.add(NextPageTemplate("body"), PageBreak())
        self.contents()
        for section in (self.summary, self.declarations, self.overview, self.now, self.trends, self.distributions, self.forecast, self.line_section, self.model, self.method, self.tech, self.human, self.annex_a, self.annex_b, self.authentication):
            section()
        return self.story

    def scope_rows(self):
        sc, s = self.sc, T["scope"]
        a, b = date_br(sc["start"]) if sc["start"] else None, date_br(sc["end"]) if sc["end"] else None
        rng = fill(s["range_both"], a=a, b=b) if a and b else fill(s["range_from"], a=a) if a else fill(s["range_to"], b=b) if b else s["range_all"]
        cams = [c for c in self.line if c["status"] == "ok"]
        ev = self.d["model"]
        model = f"{ev['configured']} · {ev['model']['architecture']}" if ev and ev.get("model") else settings.MODEL_PATH.name
        versions_ = ", ".join(v or s["unrecorded"] for v in sc["model_versions"]) or T["none"]
        return [
            (s["source"], s["sources"][sc["source"]]),
            (s["sector"], sc["sector"] or s["all_sectors"]),
            (s["period"], s["periods"][sc["period"]]),
            (s["range"], rng),
            (s["covered"], fill(s["covered_v"], a=datetime_br(sc["first"]), b=datetime_br(sc["last"])) if sc["first"] else T["none"]),
            (s["n"], num(sc["n"])),
            (s["pending"], num(sc["pending"])),
            (s["cameras"], fill(s["cameras_v"], n=len(cams), total=sc["cameras_total"]) + (f" ({', '.join(c['camera']['name'] for c in cams)})" if cams else "")),
            (s["line_n"], num(sum(c["n"] for c in self.line))),
            (s["model"], model),
            (s["versions"], versions_),
            (s["tz"], sc["time_zone"]),
        ]

    def cover(self):
        m = self.meta
        inner = PAGE_W - 42 * mm
        self.add(Spacer(1, 6 * mm))
        if m["demo"]:
            self.add(box([P(f"<b>{esc(T['demo_cover'])}</b>", "note")], WARN_BG, WARN, bar=True, pad=5, width=inner), Spacer(1, 3.5 * mm))
        self.add(P(esc(T["attest"]), "attest"), Spacer(1, 4.5 * mm), grid(self.scope_rows(), inner), Spacer(1, 5 * mm), ai_box(inner), Spacer(1, 4 * mm))
        issued = [
            P(esc(T["issued_at"]).upper(), "kv_k"), P(f"{esc(datetime_br(m['issued']))} ({esc(self.sc['time_zone'])})", "kv_v"), Spacer(1, 2),
            P(esc(T["issued_by"]).upper(), "kv_k"), P(esc(m["user"]), "kv_v"), Spacer(1, 2),
            P(esc(T["fingerprint"]).upper(), "kv_k"), P(esc(m["fingerprint"][:32]) + "<br/>" + esc(m["fingerprint"][32:]), "mono"), Spacer(1, 2),
            P(esc(T["electronic"]), "small"),
        ]
        seal, qr = 36 * mm, 25 * mm
        t = Table([[issued, QR(m["qr"], qr), Seal(seal, m["fingerprint"], m["number"])]], colWidths=[inner - seal - qr - 10 * mm, qr + 6 * mm, seal + 4 * mm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("ALIGN", (1, 0), (-1, 0), "RIGHT")]))
        self.add(Bottom(t))

    def contents(self):
        g = T["guide"]
        swatch = lambda color, label: Paragraph(f'<font color="{color}">■</font>&nbsp;{esc(label)}', S["cell"])
        items = [(C.GOOD, name("classes", "boa")), (C.POOR, name("classes", "baixa_qualidade")), (C.ROTTEN, name("classes", "podre")), (C.REVIEW, name("classes", "revisar")), (C.UP, T["growth"]["up"]), (C.DOWN, T["growth"]["down"])]
        swatches = Table([[swatch(c, l) for c, l in items]], colWidths=[W / 6] * 6)
        swatches.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1)]))
        self.add(P(esc(T["toc"]), "toc_title"), TableOfContents(levelStyles=TOC_STYLES, dotsMinLevel=0, tableStyle=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)])), Spacer(1, 6 * mm), Wave(), P(esc(g["title"]), "h2"))
        self.add(P(f"<b>{esc(g['classes'])} · {esc(g['growth'])}</b>", "small"), swatches, Spacer(1, 3 * mm), note(esc(g["warn"])), note(esc(g["info"]), "info"))
        self.add(*bullets(esc(x) for x in (g["hatch"], g["na"], g["ci"], g["tables"])))

    def kpis(self):
        k, tiles = T["kpi"], []
        if self.ok("overview"):
            o = self.dash["overview"]
            lo, hi = wilson(o["n_rotten"], o["n"])
            tiles += [(k["fruits"], num(o["n"]), k["fruits_sub"], TEAL), (k["rate"], pct(o["rotten_rate"]), fill(k["rate_sub"], lo=pct(lo), hi=pct(hi)), RED)]
        if self.ok("gaussian"):
            gs = self.dash["gaussian"]["sectors"]
            tiles.append((k["sectors"], num(len(gs)), fill(k["sectors_sub"], f=sum(s["flagged"] for s in gs)), TEAL))
        if self.ok("forecast"):
            fs = self.dash["forecast"]["sectors"]
            tiles.append((k["forecasts"], num(sum(s["reliable"] for s in fs)), fill(k["forecasts_sub"], n=len(fs)), TEAL))
        cams = [c for c in self.line if c["status"] == "ok"]
        if cams:
            verdicts = [l["verdict"] for c in cams for l in c["lots"]]
            tiles += [
                (k["line"], num(sum(c["n"] for c in cams)), fill(k["line_sub"], k=len(cams)), TEAL),
                (k["lots"], num(verdicts.count("reprovado")), fill(k["lots_sub"], n=len(verdicts), i=verdicts.count("inconclusivo")), RED),
                (k["alarms"], num(sum(len(c["p_chart"]["alarms"]) for c in cams)), k["alarms_sub"], RED),
            ]
        tiles.append((k["pending"], num(self.sc["pending"]), k["pending_sub"], TAN))
        gap = 3 * mm
        width = (W - 3 * gap) / 4
        cells = [Tile(a, b, c, d, width) for a, b, c, d in tiles]
        rows = [cells[i:i + 4] + [""] * (4 - len(cells[i:i + 4])) for i in range(0, len(cells), 4)]
        t = Table(rows, colWidths=[width + gap] * 3 + [width], rowHeights=[23 * mm + gap] * len(rows))
        t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), gap), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    def findings(self):
        f, out = T["find"], []
        if self.ok("overview"):
            o = self.dash["overview"]
            lo, hi = wilson(o["n_rotten"], o["n"])
            out.append(fill(f["rate"], v=pct(o["rotten_rate"]), lo=pct(lo), hi=pct(hi), n=num(o["n"])))
            if len(o["sectors"]) > 1:
                ranked = sorted(o["sectors"], key=lambda s: s["rotten_rate"])
                out.append(fill(f["worst"], s=ranked[-1]["sector"], v=pct(ranked[-1]["rotten_rate"]), s2=ranked[0]["sector"], v2=pct(ranked[0]["rotten_rate"])))
        if self.ok("fruits") and self.dash["fruits"]["items"]:
            top = self.dash["fruits"]["items"][0]
            out.append(fill(f["fruit"], f=name("fruits", top["fruit"]), v=pct(top["share"])))
        if self.ok("deformity"):
            d = self.dash["deformity"]
            i = next((i for i in range(len(d["n_rotten"]) - 1, -1, -1) if d["n_rotten"][i] > 0), None)
            if i is not None:
                w = period_label(d["weeks"][i], "week")
                out.append(fill(f["defect_tie"], w=w) if d["tie"][i] else fill(f["defect"], w=w, t=name("deformities", d["dominant"][i]), v=pct(d["share"][i])))
        if self.ok("forecast"):
            risky = sorted((s for s in self.dash["forecast"]["sectors"] if s["status"] == "ok"), key=lambda s: -s["p_more_rotten"])
            for s in [x for x in risky if x["p_more_rotten"] > 0.5][:2] or risky[:1]:
                out.append(fill(f["forecast"], s=s["sector"], v=pct(s["rotten_pred"]), p=prob(s["p_more_rotten"]), r=T["reliable_word"][s["reliable"]]))
        if self.ok("gaussian"):
            gs = self.dash["gaussian"]["sectors"]
            bad = [s["sector"] for s in gs if s["flagged"]]
            out.append(fill(f["gauss"], ok=len(gs) - len(bad), bad=len(bad), names=", ".join(bad) or T["none"]))
        g = self.dash["growth"]
        if g["status"] == "ok":
            out.append(fill(f["growth"], w=period_label(g["labels"][-1], self.sc["period"]), g=signed_pct(g["good"]["count_growth"][-1]), r=signed_pct(g["rotten"]["count_growth"][-1])))
        if self.ok("recurring"):
            mo = self.dash["recurring"]["month"]
            vals = [v for v in mo["rotten"] if v is not None]
            if vals:
                k = mo["rotten"].index(max(vals))
                out.append(fill(f["season"], m=bucket_label("month", mo["buckets"][k]), v=signed_pct(mo["rotten"][k])))
        for c in (c for c in self.line if c["status"] == "ok"):
            bad = [l for l in c["lots"] if l["verdict"] == "reprovado"]
            if bad and c["max_rotten"] is not None:
                l = bad[0]
                out.append(fill(f["lot"], cam=c["camera"]["name"], lot=l["lot"], v=pct(l["rotten"]["share"]), lo=pct(l["rotten"]["ci95"][0]), hi=pct(l["rotten"]["ci95"][1]), max=pct(c["max_rotten"])))
            rules = [a["rule"] for a in c["p_chart"]["alarms"]]
            if rules:
                out.append(fill(f["alarms"], cam=c["camera"]["name"], n=len(rules), a=rules.count("acima_do_limite"), r=rules.count("sequencia_acima_da_mediana")))
        return out or [f["none"]]

    def summary(self):
        self.opener(T["sections"]["scope"])
        self.add(P(esc(T["scope_lead"]), "lead"), self.kpis(), *self.h3(T["highlights"]), *bullets(esc(x) for x in self.findings()))
        self.add(*self.h3(T["scope_table"]), kv(self.scope_rows()), *self.h3(T["summary"]), table(T["summary_cols"], self.summary_rows(), [0.3, 0.26, 0.44]))

    def summary_rows(self):
        rows, s = [], T["sum"]
        if self.ok("overview"):
            o = self.dash["overview"]
            lo, hi = wilson(o["n_rotten"], o["n"])
            worst = max(o["sectors"], key=lambda x: x["rotten_rate"]) if o["sectors"] else None
            rows += [
                (s["n"], num(o["n"]), ""),
                (s["good"], f"{num(o['n_good'])} ({pct(o['n_good'] / o['n'])})", ""),
                (s["rotten"], f"{num(o['n_rotten'])} ({pct(o['n_rotten'] / o['n'])})", ""),
                (s["rate"], pct(o["rotten_rate"]), fill(s["rate_note"], lo=pct(lo), hi=pct(hi))),
                (s["sectors"], num(o["n_sectors"]), fill(s["worst"], s=worst["sector"], v=pct(worst["rotten_rate"])) if worst else ""),
                (s["top_fruit"], name("fruits", o["top_fruit"]) if o["top_fruit"] else s["tie"], ""),
                (s["top_def"], name("deformities", o["top_deformity"]) if o["top_deformity"] else (s["tie"] if o["n_rotten"] else T["none"]), ""),
            ]
        else:
            rows.append((s["no_dash"], T["none"], ""))
        if self.ok("forecast"):
            fs = self.dash["forecast"]["sectors"]
            rows.append((s["forecasts"], fill(s["forecasts_v"], ok=sum(x["status"] == "ok" for x in fs), n=len(fs)), fill(s["forecasts_note"], r=sum(x["reliable"] for x in fs))))
        if self.ok("gaussian"):
            gs = self.dash["gaussian"]["sectors"]
            rows.append((s["gauss"], fill(s["gauss_v"], f=sum(x["flagged"] for x in gs), n=len(gs)), s["gauss_note"]))
        cams = [c for c in self.line if c["status"] == "ok"]
        if cams:
            verdicts = [l["verdict"] for c in cams for l in c["lots"]]
            rows += [
                (s["line"], num(sum(c["n"] for c in cams)), ", ".join(f"{c['camera']['name']}: {num(c['n'])}" for c in cams)),
                (s["alarms"], num(sum(len(c["p_chart"]["alarms"]) for c in cams)), ""),
                (s["lots"], num(len(verdicts)), fill(s["lots_v"], a=verdicts.count("aprovado"), r=verdicts.count("reprovado"), i=verdicts.count("inconclusivo"))),
            ]
        return rows

    def declarations(self):
        d, D = T["decl"], DECLARATIONS
        self.opener(T["sections"]["declarations"])
        self.add(P(esc(d["lead"]), "lead"), ai_box(sub=False), Spacer(1, 3 * mm))
        self.add(*self.h3(d["nature_title"]), P(esc(d["nature"])))
        if self.sc["demo"]:
            self.add(note(esc(d["demo"])))
        self.add(P(esc(fill(d["review"], n=num(self.sc["pending"])))))
        self.add(*self.h3(d["status_title"]), P(esc(D["honesty"])), P(esc(D["confidence"])))
        self.add(*self.h3(d["data_title"]), P(esc(D["dataIssue"])))
        self.add(*self.h3(d["limits_title"]), P(esc(D["limits"])))
        self.add(*self.h3(d["verified"]), *bullets(esc(x) for x in D["verified"]))
        self.add(*self.h3(d["not_verified"]), *bullets(esc(x) for x in D["notVerified"]))
        self.add(*self.h3(d["pending"]), *bullets(f"<b>{esc(x['title'])}:</b> {esc(x['text'])}" for x in D["pending"]))

    def overview(self):
        t = T["overview"]
        self.opener(T["sections"]["overview"])
        self.h2(t["title"])
        self.add(P(esc(t["lead"]), "lead"))
        if not self.ok("overview"):
            self.add(P(esc(T["no_data"])))
            return
        o, period = self.dash["overview"], self.sc["period"]
        if o["n"] < 30:
            self.add(note(esc(fill(T["badges"]["small_total"], n=num(o["n"])))))
        self.add(self.chart(C.render(C.WIDTH, 60, C.overview_volume, o, period), t["volume"], clipped(C.volume_limit(o))))
        self.add(self.chart(C.render(C.WIDTH, 50, C.overview_rate, o, period), t["rate"]))
        self.add(self.chart(C.render(C.WIDTH, max(28, 10 + 7 * len(o["sectors"])), C.overview_sectors, o["sectors"]), t["sectors"]), how(t["how"]))
        rows = []
        for s in sorted(o["sectors"], key=lambda x: -x["rotten_rate"]):
            k = round(s["rotten_rate"] * s["n"])
            rows.append((s["sector"], num(s["n"]), num(k), pct(s["rotten_rate"]), ci(wilson(k, s["n"]))))
        self.add(table(t["sector_cols"], rows, [0.3, 0.16, 0.16, 0.16, 0.22], right=(1, 2, 3, 4)))
        cv = self.d["extra"]["coverage"]
        if cv:
            c = T["coverage"]
            self.h2(c["title"])
            self.add(P(esc(c["lead"]), "lead"), self.chart(C.render(C.WIDTH, max(34, 14 + 6 * len(cv["sectors"])), C.coverage, cv, period), c["title"]))
        self.sheets()

    def sheets(self):
        if not (self.ok("forecast") and self.ok("gaussian") and self.ok("overview")):
            return
        s = T["sheets"]
        self.h2(s["title"])
        self.add(P(esc(s["lead"]), "lead"))
        rates = {x["sector"]: x for x in self.dash["overview"]["sectors"]}
        gauss = {x["sector"]: x for x in self.dash["gaussian"]["sectors"]}
        g_all = self.dash["gaussian"]
        rows = []
        for f in self.dash["forecast"]["sectors"]:
            r = rates.get(f["sector"], {"n": 0, "rotten_rate": None})
            k = round((r["rotten_rate"] or 0) * r["n"])
            hist = [v for v in f["history"] if v is not None]
            g = gauss.get(f["sector"], {"flagged": True, "reasons": []})
            reason = fill(T["gaussian"]["reasons"][g["reasons"][0]], min=g_all["min_n"], alpha=num(g_all["alpha"], 2)) if g["reasons"] else ""
            forecast = f"{pct(f['rotten_pred'])} · {T['reliable_word'][f['reliable']]}" if f["status"] == "ok" else s["insufficient"]
            rows.append((f["sector"], num(r["n"]), pct(r["rotten_rate"]), ci(wilson(k, r["n"])) if r["n"] else T["none"], Spark(f["history"]), pct(hist[-1]) if hist else T["na"], forecast, f"{s['flagged']}: {reason}" if g["flagged"] else s["ok"]))
        self.add(table(s["cols"], rows, [0.09, 0.08, 0.08, 0.13, 0.19, 0.07, 0.18, 0.18], right=(1, 2, 3, 5), size=6.7))

    def now(self):
        self.opener(T["sections"]["now"])
        t = T["deformity"]
        self.h2(t["title"])
        self.add(P(esc(t["lead"]), "lead"))
        if self.ok("deformity"):
            d = self.dash["deformity"]
            latest = next((i for i in range(len(d["n_rotten"]) - 1, -1, -1) if d["n_rotten"][i] > 0), None)
            if latest is not None and d["n_rotten"][latest] < 30:
                self.add(note(esc(fill(T["badges"]["small_latest"], n=num(d["n_rotten"][latest])))))
            if len(d["types"]) == 1:
                self.add(note(esc(T["badges"]["one_type"]), "info"))
            self.add(self.chart(C.render(C.WIDTH, 66, C.deformity, d), t["title"]))
            if latest is not None:
                week = period_label(d["weeks"][latest], "week")
                self.add(P(esc(fill(t["latest_tie"], w=week) if d["tie"][latest] else fill(t["latest"], w=week, t=name("deformities", d["dominant"][latest]), s=pct(d["share"][latest]))) + ".", "small"))
            self.add(how(t["how"]))
            total = sum(d["n_rotten"])
            rows = [(name("deformities", k), num(sum(d["counts"][k])), pct(sum(d["counts"][k]) / total) if total else T["na"], num(sum(1 for i, dom in enumerate(d["dominant"]) if dom == k and not d["tie"][i]))) for k in sorted(d["types"], key=lambda k: -sum(d["counts"][k]))]
            self.add(table(t["cols"], rows, [0.34, 0.22, 0.2, 0.24], right=(1, 2, 3)))
        else:
            self.add(P(esc(T["no_data"])))
        t = T["fruits"]
        self.h2(t["title"])
        self.add(P(esc(t["lead"]), "lead"))
        if not self.ok("fruits"):
            self.add(P(esc(T["no_data"])))
            return
        f = self.dash["fruits"]
        if f["n"] < 30:
            self.add(note(esc(fill(T["badges"]["small_total"], n=num(f["n"])))))
        self.add(self.chart(C.render(C.WIDTH, 10 + 8 * len(f["items"]), C.fruits, f), t["title"]), how(t["how"]))
        self.add(table(t["cols"], [(name("fruits", i["fruit"]), num(i["n"]), pct(i["share"])) for i in f["items"]], [0.4, 0.3, 0.3], right=(1, 2)))

    def trends(self):
        self.opener(T["sections"]["trends"])
        t = T["growth"]
        self.h2(t["title"])
        self.add(P(esc(t["lead"]), "lead"))
        g = self.dash["growth"]
        period = self.sc["period"]
        if g["status"] == "no_data":
            self.add(P(esc(T["no_data"])))
        elif g["status"] != "ok":
            self.add(note(esc(t["insufficient"]), "info"))
        else:
            if g["excluded"]:
                self.add(note(esc(fill(T["badges"]["partial"], n=num(g["excluded"]))), "info"))
            if g["n_periods"] < 8:
                self.add(note(esc(fill(T["badges"]["few_periods"], n=g["n_periods"]))))
            self.add(self.chart(C.render(C.WIDTH, 100, C.growth, g, period), t["title"], clipped(C.growth_limit(g))), how(t["how"]))
            recent = list(range(max(0, len(g["labels"]) - 8), len(g["labels"])))
            self.add(P(esc(fill(t["recent"], n=len(recent))), "small"), self.growth_table(g, recent))
        t = T["recurring"]
        self.h2(t["title"])
        self.add(P(esc(t["lead"]), "lead"))
        if not self.ok("recurring"):
            self.add(P(esc(T["no_data"])))
            return
        r = self.dash["recurring"]
        self.add(how(t["how"]))
        for view, height in (("month", 56), ("season", 50), ("week", 60)):
            v = r[view]
            if not v["buckets"]:
                self.add(*self.h3(t["views"][view]), note(esc(t["empty"]), "info"))
                continue
            notes = clipped(C.recurring_limit(r, view))
            if v["max_n"] < 2:
                notes.append(note(esc(fill(T["badges"]["recurring_small"], n=v["max_n"]))))
            if v["excluded"]:
                notes.append(note(esc(fill(T["badges"]["partial"], n=num(v["excluded"]))), "info"))
            self.add(self.chart(C.render(C.WIDTH, height, C.recurring, r, view), t["views"][view], notes))
            self.add(P(esc(t["week_annex"]), "small") if view == "week" else self.recurring_table(r, view))

    def growth_table(self, g, idx):
        rows = [(period_label(g["labels"][i], self.sc["period"]), num(g["good"]["count"][i]), signed_pct(g["good"]["count_growth"][i]), signed_pct(g["good"]["prop_growth"][i]), num(g["rotten"]["count"][i]), signed_pct(g["rotten"]["count_growth"][i]), signed_pct(g["rotten"]["prop_growth"][i])) for i in idx]
        return table(T["growth"]["cols"], rows, [0.16, 0.13, 0.14, 0.15, 0.13, 0.14, 0.15], right=(1, 2, 3, 4, 5, 6))

    def recurring_table(self, r, view):
        v = r[view]
        rows = [(bucket_label(view, b), signed_pct(v["good"][i]), num(v["good_n"][i]), signed_pct(v["rotten"][i]), num(v["rotten_n"][i])) for i, b in enumerate(v["buckets"])]
        head = [fill(T["recurring"]["cols"][0], view=T["recurring"]["views"][view])] + T["recurring"]["cols"][1:]
        return table(head, rows, [0.28, 0.18, 0.18, 0.18, 0.18], right=(1, 2, 3, 4))

    def distributions(self):
        t = T["gaussian"]
        self.opener(T["sections"]["distributions"])
        self.h2(t["title"])
        self.add(P(esc(t["lead"]), "lead"))
        if not self.ok("gaussian"):
            self.add(P(esc(T["no_data"])))
            return
        g = self.dash["gaussian"]
        self.add(how(t["how"]))
        rows = []
        for s in g["sectors"]:
            reasons = "; ".join(fill(t["reasons"][r], min=g["min_n"], alpha=num(g["alpha"], 2)) for r in s["reasons"])
            rows.append((s["sector"], num(s["n"]), pct(s["mean"]), pp(s["std"], 1, signed=False), dec(s["shapiro_w"]), pvalue(s["shapiro_p"]), pct(s["mass_outside_01"]), f"{t['flagged']}: {reasons}" if s["flagged"] else t["ok"]))
        self.add(table(t["cols"], rows, [0.1, 0.09, 0.08, 0.1, 0.09, 0.09, 0.12, 0.33], right=(1, 2, 3, 4, 5, 6)))
        if not all(s["flagged"] for s in g["sectors"]):
            self.add(P(esc(t["unflagged"]), "small"))
        for s in g["sectors"]:
            if s.get("hist"):
                self.add(self.chart(C.render(C.WIDTH, 60, C.gaussian, s), s["sector"]))
            else:
                self.add(note(esc(fill(t["empty"], s=s["sector"], n=s["n"])), "info"))

    def forecast(self):
        t = T["forecast"]
        self.opener(T["sections"]["forecast"])
        self.h2(t["title"])
        self.add(P(esc(fill(t["lead"], w=C.FORECAST_WINDOW)), "lead"))
        if not self.ok("forecast"):
            self.add(P(esc(T["no_data"])))
            return
        f, period = self.dash["forecast"], self.sc["period"]
        self.add(P(esc(fill(t["target"], p=period_label(f["target_period"], period))), "small"), how(t["how"]))
        sectors = f["sectors"]
        for i in range(0, len(sectors), 2):
            self.add(self.chart(C.render(C.WIDTH, 56, C.forecast_row, sectors[i:i + 2], f["labels"], f["target_period"], period, f["min_periods"], f["min_fruits"]), " · ".join(s["sector"] for s in sectors[i:i + 2])))
        rows = []
        for s in sectors:
            ok = s["status"] == "ok"
            state = t["reliable"] if s["reliable"] else t["insufficient"] if not ok else t["unreliable"]
            rows.append((s["sector"], num(s["n_periods"]), num(s["fruits"]), pp(s["slope"]) if ok else T["none"], pct(s["rotten_pred"]) if ok else T["none"], ci((s["rotten_lo"], s["rotten_hi"])) if ok else T["none"], prob(s["p_more_rotten"]) if ok else T["none"], pp(s["bt_mae"], 1, False) if ok else T["none"], pp(s["bt_naive_mae"], 1, False) if ok else T["none"], state))
        self.add(table(t["cols"], rows, [0.085, 0.09, 0.085, 0.1, 0.09, 0.13, 0.085, 0.1, 0.09, 0.145], right=(1, 2, 3, 4, 5, 6, 7, 8), size=6.7))
        bad = [s for s in sectors if s["reasons"]]
        if bad:
            self.add(*self.h3(t["reasons_title"]), *bullets(f"<b>{esc(s['sector'])}:</b> " + esc("; ".join(fill(t["reasons"][r], min=f["reliable_min_periods"]) for r in s["reasons"])) for s in bad))
        self.add(note(esc(t["note"]), "info"))

    def line_section(self):
        t, more = T["line"], T["line_more"]
        self.opener(T["sections"]["line"])
        self.add(P(esc(t["lead"]), "lead"), how(t["how"]))
        if not self.line:
            self.add(P(esc(t["none"])))
        for c in self.line:
            cam = c["camera"]
            self.h2(f"{cam['name']} ({cam['line']})")
            if c["status"] != "ok":
                self.add(P(esc(fill(t["no_data"], cam=cam["name"]))))
                continue
            w = c["window_minutes"]
            self.add(P(esc(fill(t["period"], a=datetime_br(c["start"]), b=datetime_br(c["end"]), w=minutes_label(w), k=num(len(c["windows"])))), "small"))
            if c["demo"]:
                self.add(note(esc(T["badges"]["demo"])))
            rows = [
                (t["registered"], num(c["n"]), ""),
                (t["complete"], num(c["total"]), ""),
                (t["throughput"], num(c["throughput_per_min"], 1) if c["throughput_per_min"] is not None else T["none"], ""),
                *[(name("classes", k), pct(c["shares"][k]["share"]), ci(c["shares"][k]["ci95"])) for k in ("boa", "baixa_qualidade", "podre")],
                (t["review"], f"{pct(c['review_share'])} ({num(c['counts']['revisar'])})", ""),
                (t["size"], fill(t["size_v"], m=num(c["size_mm"]["median"]), lo=num(c["size_mm"]["p10"]), hi=num(c["size_mm"]["p90"]), n=num(c["size_mm"]["n"])) if c["size_mm"] else T["none"], ""),
                (t["max"], pct(c["max_rotten"]) if c["max_rotten"] is not None else T["none"], ""),
            ]
            self.add(table(t["kpi_cols"], rows, [0.4, 0.34, 0.26], right=(1, 2)))
            if c["windows"]:
                self.add(self.chart(C.render(C.WIDTH, 60, C.line_flow, c), t["flow"]), self.chart(C.render(C.WIDTH, 60, C.line_pchart, c), t["pchart"]))
            if c.get("size_hist") and sum(sum(v) for v in c["size_hist"]["counts"].values()):
                self.add(self.chart(C.render(C.WIDTH, 52, C.sizes, c), more["sizes"]))
            self.add(*self.h3(t["alarms"]))
            alarms = c["p_chart"]["alarms"]
            if alarms:
                label = (lambda s: datetime_br(s)) if w >= 1440 else (lambda s: f"{date_br(s)} {clock(s)}")
                self.add(*bullets(esc(fill(t["alarm_text"][a["rule"]], time=label(c["windows"][a["index"]]["start"]), p=pct(c["p_chart"]["p"][a["index"]]))) for a in alarms))
            else:
                self.add(P(esc(t["no_alarms"])))
            self.add(CondPageBreak((60 + 7 * len(c["lots"])) * mm), *self.h3(t["lots"]))
            if c["lots"]:
                self.add(P(esc(fill(t["lots_lead"], max=pct(c["max_rotten"]) if c["max_rotten"] is not None else T["none"])), "small"))
                if c["max_rotten"] is not None:
                    self.add(self.chart(C.render(C.WIDTH, 14 + 7 * len(c["lots"]), C.lots, c), more["acceptance"], [P(esc(more["acceptance_lead"]), "small")]))
                rows = [(l["lot"], datetime_br(l["first"]), datetime_br(l["last"]), num(l["n"]), pct(l["rotten"]["share"]), ci(l["rotten"]["ci95"]), pct(l["poor"]["share"]), t["verdicts"].get(l["verdict"], l["verdict"])) for l in c["lots"]]
                self.add(table(t["lot_cols"], rows, [0.13, 0.15, 0.15, 0.08, 0.09, 0.16, 0.11, 0.13], right=(3, 4, 5, 6), size=6.8))
            else:
                self.add(P(esc(t["lots_empty"])))

    def model(self):
        t = T["model"]
        self.opener(T["sections"]["model"])
        self.add(P(esc(t["lead"]), "lead"))
        ev = self.d["model"]
        if not ev or not ev.get("test"):
            self.add(note(esc(t["missing"])))
            return
        if ev["model"]["file"] != ev["configured"]:
            self.add(note(esc(fill(t["mismatch"], a=ev["model"]["file"], b=ev["configured"]))))
        m, ts, belt = ev["model"], ev["test"], ev.get("belt") or {}
        rej = ts["with_reject"]
        rows = [
            (t["file"], m["file"], ""),
            (t["arch"], m["architecture"], f"{m['img_size']} px"),
            (t["classes"], ", ".join(name("classes", c) for c in m["classes"]), ""),
            (t["split"], t["split_v"], ""),
            (t["test_n"], fill(t["test_n_v"], n=num(ts["n"]), p=num(ts["photos"])), ""),
            (t["acc"], pct(ts["accuracy"]), fill(t["acc_note"], lo=pct(ts["accuracy_ci95"][0]), hi=pct(ts["accuracy_ci95"][1]))),
            (t["bal"], pct(ts["balanced_accuracy"]), t["bal_note"]),
            (t["base"], pct(ts["majority_baseline_accuracy"]), t["base_note"]),
            *[(fill(t["recall"], c=name("classes", k)), pct(v), "") for k, v in ts["recall"].items()],
            *[(fill(t["precision"], c=name("classes", k)), pct(v), "") for k, v in ts["precision"].items()],
            (t["rg"], pct(ts["rotten_as_good"]["k"] / ts["rotten_as_good"]["n"]), fill(t["rg_note"], k=num(ts["rotten_as_good"]["k"]), n=num(ts["rotten_as_good"]["n"]), lo=pct(ts["rotten_as_good"]["rate_ci95"][0]), hi=pct(ts["rotten_as_good"]["rate_ci95"][1]))),
            (t["ece"], pct(ts["ece"]), fill(t["ece_note"], u=pct(ts["ece_uncalibrated"]))),
            (t["reject"], pct(rej["threshold"], 0) if rej["threshold"] is not None else t["reject_none"], ""),
        ]
        if belt.get("counting"):
            bc, mv = belt["counting"], belt["multi_view"]
            rows += [
                (t["belt_count"], fill(t["belt_count_v"], c=num(bc["counted"]), x=num(bc["fruits_that_crossed_the_line"]), d=num(bc["double_counts"])), ""),
                (t["belt_acc"], pct(mv["accuracy"]), fill(t["belt_acc_note"], lo=pct(mv["accuracy_ci95"][0]), hi=pct(mv["accuracy_ci95"][1]))),
            ]
        self.add(table(t["cols"], rows, [0.36, 0.3, 0.34]))

    def method(self):
        self.opener(T["sections"]["method"])
        values = {"fruits": 30, "min": 20, "alpha": "0,05", "outside": "1%", "min_p": 8, "reliable": 20}
        f = self.dash.get("forecast", {})
        g = self.dash.get("gaussian", {})
        if f.get("status") == "ok":
            values.update(fruits=f["min_fruits"], min_p=f["min_periods"], reliable=f["reliable_min_periods"])
        if g.get("status") == "ok":
            values.update(min=g["min_n"], alpha=num(g["alpha"], 2), outside=pct(g["max_outside"], 0))
        rows = [[Paragraph(esc(k).upper(), S["kv_k"]), Paragraph(esc(v.format(**values)), S["kv_v"])] for k, v in T["method"]]
        t = Table(rows, colWidths=[0.26 * W, 0.74 * W])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE), ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
        self.add(t)

    def tech(self):
        t, m = T["tech"], self.meta
        self.opener(T["sections"]["tech"])
        self.add(P(esc(t["lead"]), "lead"))
        self.add(*self.h3(t["doc"]), kv([
            (t["generator"], fill(t["generator_v"], v=VERSION)),
            (t["fonts"], t["fonts_v"] if BRANDED else t["fonts_fallback"]),
            (T["auth"]["number"], m["number"]),
            (T["auth"]["fingerprint"], P(esc(m["fingerprint"]), "mono")),
        ]))
        self.add(*self.h3(t["data"]), kv([
            (t["rows"], fill(t["rows_v"], n=num(self.sc["n"]), p=num(self.sc["pending"]), l=num(sum(c["n"] for c in self.line)))),
            (t["period"], T["scope"]["periods"][self.sc["period"]]),
            (T["scope"]["tz"], self.sc["time_zone"]),
        ]))
        digest = model_hash()
        self.add(*self.h3(t["model"]), kv([(t["model_file"], settings.MODEL_PATH.name), (t["model_hash"], P(esc(digest), "mono") if digest else t["model_missing"])]))
        self.add(*self.h3(t["params"]), kv([
            (t["min_periods"], num(FA.MIN_PERIODS)),
            (t["reliable_periods"], num(FA.MIN_GAUSS_N)),
            (t["min_fruits"], num(FA.MIN_FRUITS)),
            (t["gauss_n"], num(FA.MIN_GAUSS_N)),
            (t["alpha"], num(FA.ALPHA, 2)),
            (t["outside"], pct(FA.MAX_OUTSIDE, 0)),
            (t["z"], f"z = {num(BS.Z, 2)}"),
            (t["run"], fill(t["run_v"], n=BS.RUN)),
            (t["sigma"], t["sigma_v"]),
            (t["windows"], fill(t["windows_v"], n=MAX_LINE_WINDOWS)),
        ]))
        self.add(*self.h3(t["software"]), kv(versions()))

    def human(self):
        h = T["human"]
        self.opener(T["sections"]["human"])
        self.add(P(esc(h["lead"]), "lead"), Spacer(1, 4 * mm))
        rows = [[Paragraph(esc(k).upper(), S["kv_k"]), ""] for k in (h["name"], h["role"], h["date"], h["signature"])]
        t = Table(rows, colWidths=[30 * mm, W - 30 * mm], rowHeights=[13 * mm] * 4)
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LINEBELOW", (1, 0), (1, -1), 0.6, INK), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        notes = Table([[Paragraph(esc(h["notes"]).upper(), S["kv_k"])]] + [[""] for _ in range(5)], colWidths=[W], rowHeights=[7 * mm] + [9 * mm] * 5)
        notes.setStyle(TableStyle([("LINEBELOW", (0, 1), (-1, -1), 0.4, RULE), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
        self.add(t, Spacer(1, 8 * mm), notes)

    def annex_a(self):
        a = T["annex"]
        self.opener(T["sections"]["annex_a"], numbered=False, tab="A")
        self.add(P(esc(a["lead"]), "lead"))
        period = self.sc["period"]
        if self.ok("overview"):
            o = self.dash["overview"]
            rows = [(period_label(l, period), num(gd), num(rt), num(gd + rt), pct(rt / (gd + rt)) if gd + rt else T["na"]) for l, gd, rt in zip(o["labels"], o["good"], o["rotten"])]
            self.h2(a["overview"])
            self.add(table(a["overview_cols"], rows, [0.24, 0.19, 0.19, 0.19, 0.19], right=(1, 2, 3, 4)))
        if self.ok("deformity"):
            d = self.dash["deformity"]
            types = d["types"]
            rows = [(period_label(wk, "week"), num(d["n_rotten"][i]), (T["sum"]["tie"] if d["tie"][i] else name("deformities", d["dominant"][i])) if d["n_rotten"][i] else T["none"], pct(d["share"][i]), *[num(d["counts"][k][i]) for k in types]) for i, wk in enumerate(d["weeks"])]
            rest = (1 - 0.46) / max(1, len(types))
            self.h2(a["deformity"])
            self.add(table(a["deformity_cols"] + [name("deformities", k) for k in types], rows, [0.1, 0.09, 0.13, 0.14] + [rest] * len(types), right=tuple([1, 3] + list(range(4, 4 + len(types))))))
        g = self.dash["growth"]
        if g["status"] == "ok":
            self.h2(a["growth"])
            self.add(self.growth_table(g, range(len(g["labels"]))))
        if self.ok("recurring") and self.dash["recurring"]["week"]["buckets"]:
            self.h2(a["recurring"])
            self.add(self.recurring_table(self.dash["recurring"], "week"))
        if self.ok("forecast"):
            f = self.dash["forecast"]
            secs = f["sectors"]
            self.h2(a["props"])
            self.add(P(esc(fill(a["props_note"], fruits=f["min_fruits"])), "small"))
            for k in range(0, len(secs), 6):
                chunk = secs[k:k + 6]
                rows = [(period_label(l, period), *[pct(s["history"][i]) for s in chunk]) for i, l in enumerate(f["labels"])]
                self.add(table([a["period"]] + [s["sector"] for s in chunk], rows, [0.16] + [0.84 / len(chunk)] * len(chunk), right=tuple(range(1, len(chunk) + 1))), Spacer(1, 3 * mm))

    def annex_b(self):
        cams = [c for c in self.line if c["status"] == "ok" and c["windows"]]
        if not cams:
            return
        t = T["line"]
        self.opener(T["sections"]["annex_b"], numbered=False, tab="B")
        for c in cams:
            self.h2(f"{c['camera']['name']} ({c['camera']['line']})")
            alarms = {a["index"] for a in c["p_chart"]["alarms"]}
            daily = c["window_minutes"] >= 1440
            rows = []
            for i, w in enumerate(c["windows"]):
                decided = w["n"] - w["revisar"]
                rows.append((date_br(w["start"]) if daily else f"{date_br(w['start'])} {clock(w['start'])}", num(w["n"]), num(w["boa"]), num(w["baixa_qualidade"]), num(w["podre"]), num(w["revisar"]), pct(w["podre"] / decided) if decided else T["na"], pct(c["p_chart"]["ucl"][i]), "◆" if i in alarms else ""))
            self.add(table(t["window_cols"], rows, [0.19, 0.09, 0.09, 0.11, 0.09, 0.09, 0.11, 0.13, 0.1], right=(1, 2, 3, 4, 5, 6, 7), size=6.8))

    def authentication(self):
        a, m = T["auth"], self.meta
        self.opener(T["sections"]["auth"], numbered=False, tab=T["annex_tab"]["auth"], kicker=T["brand"].upper())
        self.add(P(esc(a["lead"]), "lead"))
        seal, qr = 62 * mm, 40 * mm
        row = Table([[Seal(seal, m["fingerprint"], m["number"]), QR(m["qr"], qr)]], colWidths=[W / 2, W / 2])
        row.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        captions = Table([[P(esc(a["rosette"]), "small"), P(esc(a["qr"]), "small")]], colWidths=[W / 2, W / 2])
        captions.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10)]))
        self.add(row, captions, Spacer(1, 4 * mm))
        self.add(kv([(a["number"], m["number"]), (a["issued"], f"{datetime_br(m['issued'])} ({self.sc['time_zone']})"), (a["user"], m["user"]), (a["fingerprint"], P(esc(m["fingerprint"]), "mono"))]))
        self.add(Spacer(1, 3 * mm), P(esc(a["check"])), Spacer(1, 4 * mm), ai_box())


def certificate_number(fingerprint, issued, user):
    tag = hashlib.sha256(f"{fingerprint}|{issued.isoformat()}|{user}".encode("utf-8")).hexdigest()[:8].upper()
    return f"FC-{issued:%Y%m%d}-{tag}"


def qr_payload(data, number, issued):
    sc, s = data["scope"], T["scope"]
    scope = " / ".join((s["sources"][sc["source"]], sc["sector"] or s["all_sectors"], s["periods"][sc["period"]], f"{sc['start'] or '...'} a {sc['end'] or '...'}"))
    lines = [f"{T['brand']} - {T['title']}", f"No {number}", f"Emitido {issued:%Y-%m-%d %H:%M} ({sc['time_zone']})", f"Escopo: {scope}", f"Frutas: {sc['n']} painel, {sum(c['n'] for c in data['line'])} cameras", f"SHA-256: {data['fingerprint']}"]
    return ascii_text("\n".join(lines))


def render(data, user, issued):
    issued = issued.replace(tzinfo=None) if issued.tzinfo else issued
    number = certificate_number(data["fingerprint"], issued, user)
    meta = {"number": number, "user": user, "issued": issued, "fingerprint": data["fingerprint"], "demo": data["scope"]["demo"], "qr": qr_payload(data, number, issued), "tabs": []}
    buf = io.BytesIO()
    doc = Doc(buf, meta)
    doc.setProgressCallBack(lambda kind, n: setattr(doc, "draft", n == 1) if kind == "PASS" else None)
    doc.multiBuild(Builder(data, meta).build(), canvasmaker=numbered_canvas())
    return buf.getvalue(), number
