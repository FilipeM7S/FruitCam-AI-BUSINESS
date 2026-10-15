import io
import sys
from pathlib import Path
from urllib.request import urlopen

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "brand" / "fonts"
WEB = ROOT / "frontend" / "src" / "fonts"
TEXTS = ROOT / "legal" / "texts"
WEB_TEXT = "".join(chr(c) for c in range(0x20, 0x7F)) + "ÁÀÂÃÉÊÍÓÔÕÚÇáàâãéêíóôõúçºª–—‘’“”…·•"
BASE = "https://github.com/google/fonts/raw/main/ofl"
SOURCES = {
    "fraunces": ("fraunces/Fraunces%5BSOFT,WONK,opsz,wght%5D.ttf", "fraunces/OFL.txt"),
    "fraunces-italic": ("fraunces/Fraunces-Italic%5BSOFT,WONK,opsz,wght%5D.ttf", None),
    "inter": ("inter/Inter%5Bopsz,wght%5D.ttf", "inter/OFL.txt"),
    "jetbrainsmono": ("jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf", "jetbrainsmono/OFL.txt"),
}
INSTANCES = {
    "Fraunces-Display.ttf": ("fraunces", {"opsz": 72, "wght": 620, "SOFT": 40, "WONK": 0}, "Fraunces Display", "SemiBold"),
    "Fraunces-Text.ttf": ("fraunces", {"opsz": 14, "wght": 420, "SOFT": 30, "WONK": 0}, "Fraunces Text", "Regular"),
    "Fraunces-TextItalic.ttf": ("fraunces-italic", {"opsz": 14, "wght": 400, "SOFT": 30, "WONK": 0}, "Fraunces Text", "Italic"),
    "Inter-Regular.ttf": ("inter", {"opsz": 14, "wght": 400}, "Inter", "Regular"),
    "Inter-Medium.ttf": ("inter", {"opsz": 14, "wght": 500}, "Inter", "Medium"),
    "Inter-SemiBold.ttf": ("inter", {"opsz": 14, "wght": 600}, "Inter", "SemiBold"),
    "Inter-Bold.ttf": ("inter", {"opsz": 14, "wght": 700}, "Inter", "Bold"),
    "JetBrainsMono-Regular.ttf": ("jetbrainsmono", {"wght": 400}, "JetBrains Mono", "Regular"),
    "JetBrainsMono-SemiBold.ttf": ("jetbrainsmono", {"wght": 600}, "JetBrains Mono", "SemiBold"),
}


def fetch(path):
    with urlopen(f"{BASE}/{path}", timeout=60) as r:
        return r.read()


def rename(font, family, style):
    for rec in font["name"].names:
        if rec.nameID in (1, 16):
            rec.string = family
        elif rec.nameID in (2, 17):
            rec.string = style
        elif rec.nameID == 4:
            rec.string = f"{family} {style}"
        elif rec.nameID == 6:
            rec.string = f"{family.replace(' ', '')}-{style}-FruitCam"


def web_font():
    WEB.mkdir(parents=True, exist_ok=True)
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = ["kern", "liga"]
    font = subset.load_font(str(OUT / "Fraunces-Display.ttf"), options)
    sub = subset.Subsetter(options)
    sub.populate(text=WEB_TEXT)
    sub.subset(font)
    subset.save_font(font, str(WEB / "fraunces-display.woff2"), options)
    print(f"fraunces-display.woff2 {(WEB / 'fraunces-display.woff2').stat().st_size:>8d} B  (Latin + Portuguese subset for the site)")


def main():
    if "--web-only" in sys.argv:
        web_font()
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    TEXTS.mkdir(parents=True, exist_ok=True)
    variable = {}
    for key, (font, license_path) in SOURCES.items():
        variable[key] = fetch(font)
        if license_path:
            (TEXTS / f"OFL-{key}.txt").write_bytes(fetch(license_path))
    for name, (key, location, family, style) in INSTANCES.items():
        static = instancer.instantiateVariableFont(TTFont(io.BytesIO(variable[key])), location, updateFontNames=False)
        rename(static, family, style)
        static.save(OUT / name)
        print(f"{name:28s} {(OUT / name).stat().st_size:>8d} B  {location}")
    web_font()
    return 0


if __name__ == "__main__":
    sys.exit(main())
