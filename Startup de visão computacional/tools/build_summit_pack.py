import json
import re
import shutil
from pathlib import Path

import matplotlib
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "summit_pack"
PUBLIC = ROOT / "frontend" / "public"
FRONT = ROOT / "frontend" / "src"
VIDEO = ROOT / "media_src" / "video"
COMMONS = ROOT / "media_src" / "commons"
FONTS = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
LABELS = {"schematic": "Esquema, sem dados", "synthetic": "Dados sintéticos", "real": "Medição real", "example": "Exemplo real, não é métrica", "test": "Medição real (teste)", "simulation": "Simulação"}
PHOTOS = [
    ("caju-arvore", "01-cajus-no-cajueiro"),
    ("caju-pacajus", "02-plantacao-de-caju-pacajus"),
]
SCREENS = [
    ("app-linha.png", "03-app-linha-camera-simulada.png", "Monitor da linha no app real: câmera simulada, indicadores e gráficos com dados sintéticos (selo visível)."),
    ("app-resultado.png", "04-app-inspecao-por-foto.png", "Inspeção por foto no app real: foto de caju (Wilfredor, CC0) com as probabilidades das três classes devolvidas pelo modelo."),
]
STORY = [
    ("1-linha.png", "1. Página Linha: câmera sobre a esteira"),
    ("2-monitor.png", "2. Monitor ao vivo (câmera simulada)"),
    ("3-camera.png", "3. Como a câmera funciona"),
    ("4-inspecao.png", "4. Inspeção por foto, três classes"),
]


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return dst


def storyboard(out):
    font = ImageFont.truetype(str(FONTS / "DejaVuSans-Bold.ttf"), 28)
    note = ImageFont.truetype(str(FONTS / "DejaVuSans.ttf"), 22)
    tile_w, tile_h, pad, label = 960, 540, 32, 56
    sheet = Image.new("RGB", (2 * tile_w + 3 * pad, 2 * (tile_h + label) + 3 * pad + 48), "#f5f1e6")
    draw = ImageDraw.Draw(sheet)
    for i, (name, caption) in enumerate(STORY):
        x = pad + (i % 2) * (tile_w + pad)
        y = pad + (i // 2) * (tile_h + label + pad)
        with Image.open(VIDEO / "storyboard" / name) as im:
            sheet.paste(im.convert("RGB").resize((tile_w, tile_h), Image.LANCZOS), (x, y + label))
        draw.text((x, y + 12), caption, font=font, fill="#14231e")
        draw.rectangle([x - 1, y + label - 1, x + tile_w, y + label + tile_h], outline="#c9c2b0", width=2)
    draw.text((pad, sheet.height - 52), "Capturas do app real em execução. Câmera e dados da linha simulados; foto da inspeção: Wilfredor, CC0.", font=note, fill="#5a6458")
    sheet.save(out, optimize=True)


def vtt_lines(path):
    blocks = path.read_text(encoding="utf-8").strip().split("\n\n")[1:]
    return [(b.splitlines()[0].split(" --> ")[0], b.splitlines()[1]) for b in blocks]


def main():
    figures = json.loads((FRONT / "figures.json").read_text(encoding="utf-8"))
    licenses = json.loads((FRONT / "licenses.json").read_text(encoding="utf-8"))
    brand = json.loads((FRONT / "brand.json").read_text(encoding="utf-8"))
    demo = json.loads((VIDEO / "demo.json").read_text(encoding="utf-8"))
    third = {item["id"]: item for item in licenses["third_party"]}
    shutil.rmtree(PACK, ignore_errors=True)
    PACK.mkdir()
    placed = {}

    lines = ["# Legendas das figuras", "", "Geradas por `figures/make_figures.py`. Cada figura traz no canto inferior direito o rótulo da origem dos dados; mantenha esse rótulo e a legenda ao usar a figura.", ""]
    for name in figures["order"]:
        f = figures["items"][name]
        for ext in ("svg", "png"):
            copy(ROOT / "figures" / "out" / f"{name}.{ext}", PACK / "figuras" / f"{name}.{ext}")
        lines += [f"## Figura {f['number']}. {f['title']}", "", f"Rótulo: **{LABELS[f['label']]}**. Arquivos: `{name}.svg` (vetorial) e `{name}.png` (300 dpi, 183 mm de largura).", "", f["caption"], "", f"Texto alternativo: {f['alt']}", ""]
        for asset in f["assets"]:
            placed.setdefault(asset, []).append(f"figuras/{name}.svg e .png")
    (PACK / "figuras" / "LEGENDAS.md").write_text("\n".join(lines), encoding="utf-8")

    logos = {
        "logo-sobre-claro.png": "logo-on-light.png",
        "logo-sobre-escuro.png": "logo-on-dark.png",
        "icone-app.png": "app-icon.png",
        "icone-512.png": "icon-512.png",
        "icone-maskable-512.png": "icon-maskable-512.png",
        "favicon.ico": "favicon.ico",
        "imagem-compartilhamento-1200x630.png": "og-image.png",
    }
    for dst, src in logos.items():
        copy(PUBLIC / "brand" / src, PACK / "logo" / dst)

    masters = set()
    for asset, stem in PHOTOS:
        meta = third[asset]
        out = copy(COMMONS / f"{asset}.jpg", PACK / "imagens" / f"{stem}-{slug(meta['author'])[:24]}-{slug(meta['license'])}.jpg")
        placed.setdefault(asset, []).append(f"imagens/{out.name}")
        masters.add(asset)
    hero = json.loads((VIDEO / "hero" / "hero.json").read_text(encoding="utf-8"))
    for src, dst, _ in SCREENS:
        copy(VIDEO / "hero" / src, PACK / "imagens" / dst)
        for asset in hero[src]:
            placed.setdefault(asset, []).append(f"imagens/{dst} (na interface)")

    for name in ("demo.mp4", "demo.webm", "demo.vtt", "demo-poster.png", "pipeline.mp4", "pipeline.gif", "belt-sim.mp4", "belt-sim.webm"):
        copy(VIDEO / name, PACK / "video" / name)
    for name, _ in STORY:
        copy(VIDEO / "storyboard" / name, PACK / "video" / "storyboard" / name)
    storyboard(PACK / "video" / "storyboard.png")
    for asset in demo["contains"]:
        placed.setdefault(asset, []).append("video/demo.mp4 e demo.webm (na interface gravada)")
    for asset in demo["poster"]:
        placed.setdefault(asset, []).append("video/demo-poster.png (na interface)")
    for name, assets in demo["stills"].items():
        for asset in assets:
            placed.setdefault(asset, []).append(f"video/storyboard/{name}.png e video/storyboard.png (na interface)")
    cues = vtt_lines(VIDEO / "demo.vtt")
    (PACK / "video" / "TRANSCRICAO.md").write_text("\n".join(["# Transcrição do vídeo de demonstração", "", f"`demo.mp4` / `demo.webm`: {demo['width']}×{demo['height']} px, {demo['duration']} s, sem áudio. Legendas em `demo.vtt` (pt-BR).", "", demo["caption"], ""] + [f"- **{t}** {text}" for t, text in cues] + ["", "`pipeline.mp4` / `pipeline.gif`: animação das 7 etapas do caminho de uma foto, gravada da página Como funciona (sem dados).", ""]), encoding="utf-8")

    rows = ["# Licenças e créditos do kit", "", "Tudo neste kit é material próprio da FruitCam, exceto as fotos de terceiros abaixo, todas da Wikimedia Commons com licença que permite este uso. Ao publicar uma foto de terceiros, ou uma captura em que ela apareça, inclua o crédito indicado. Fotos CC BY-SA: adaptações delas (recortes, montagens) devem ser compartilhadas sob a mesma licença.", "", "## Fotos de terceiros", ""]
    for asset, where in sorted(placed.items()):
        meta = third[asset]
        rows += [f"### {meta['title']}", "", f"- Crédito: {meta['attribution_text']}", f"- Autor: {meta['author']}", f"- Licença: [{meta['license']}]({meta['license_url']})", f"- Fonte: {meta['source_url']}", f"- Data original: {meta['date'] or '—'}; obtida em {meta['retrieved']}", f"- Modificações no app: {meta['modifications']}", *([f"- Arquivo em imagens/: original reduzido para no máximo 2560 px e sem metadados, sem recorte."] if asset in masters else []), f"- Onde está no kit: {'; '.join(sorted(set(where)))}", "- Uso: imagem ilustrativa; não é foto de cliente, fábrica ou operação real da FruitCam.", ""]
    rows += ["## Material próprio", ""]
    for item in licenses["first_party"]:
        rows += [f"- **{item['title']}**: {item['license']}. {item['note']}"]
    rows += ["", "Fonte deste arquivo: `frontend/src/licenses.json` (gerado por `tools/build_media.py`).", ""]
    (PACK / "LICENCAS.md").write_text("\n".join(rows), encoding="utf-8")

    rules = brand["rules"]
    readme = [
        "# Kit de materiais FruitCam_ai para o Siará Tech Summit",
        "",
        "Gerado por `tools/build_summit_pack.py` a partir dos mesmos arquivos usados no app. Para atualizar, rode de novo os scripts (ver MEDIA.md na raiz do projeto).",
        "",
        "## Conteúdo",
        "",
        "- `figuras/`: 8 figuras científicas em SVG e PNG 300 dpi, com `LEGENDAS.md`.",
        "- `logo/`: logotipo sobre fundo claro e escuro, ícone do app, ícones 512 px, favicon e imagem de compartilhamento.",
        "- `imagens/`: 2 fotos ilustrativas de terceiros (com crédito obrigatório) e 2 capturas do app (linha com câmera simulada e inspeção por foto).",
        "- `video/`: demonstração gravada do app (MP4 e WebM, sem áudio, com legendas e transcrição), storyboard em 4 quadros, a animação das etapas (MP4 e GIF) e a simulação da esteira vista pela câmera (MP4 e WebM).",
        "- `LICENCAS.md`: autor, licença, fonte e modificações de cada foto de terceiros.",
        "",
        "## Regras de uso",
        "",
        f"- Logotipo: use o arquivo do fundo correspondente (claro ou escuro), sem recolorir, distorcer ou redesenhar. Margem livre mínima em volta: {rules['clearSpace']}× a altura do desenho. Altura mínima do desenho: {rules['minInkHeightPx']['lockup']} px (logotipo) e {rules['minInkHeightPx']['icon']} px (ícone).",
        "- Os logotipos são recortes provisórios da imagem do kit enviada pela equipe (PNG); substitua pelos arquivos vetoriais originais assim que existirem.",
        "- Fotos de terceiros: sempre com o rótulo “Imagem ilustrativa” e o crédito de `LICENCAS.md`. Não apresente como foto de campo, cliente ou fábrica.",
        "- Figuras 3, 4 e 5 e a captura do painel usam dados sintéticos: mantenha o rótulo. A Figura 6 é medição real em fotos de campo de teste (separadas por foto); cite as limitações da legenda.",
        "- As capturas da linha usam uma câmera simulada e dados sintéticos: mantenha o selo. O classificador atual é fraco (acurácia balanceada perto de 50% em fotos de campo, com o acaso em 33%) e manda toda fruta para conferência manual; os dados públicos de treino tinham a numeração de classes trocada em 1.466 de 3.098 fotos, e um número antigo de 80,9% de acerto vinha desse erro: não o use. Não apresente números de desempenho em esteira real: eles ainda não existem.",
        "- Não há clientes, fábricas, parceiros ou números de desempenho em campo: não os mencione.",
        "",
        "## Arquivos",
        "",
    ]
    total = 0
    for path in sorted(p for p in PACK.rglob("*") if p.is_file()):
        size = path.stat().st_size
        total += size
        detail = ""
        if path.suffix in (".png", ".jpg", ".gif"):
            with Image.open(path) as im:
                detail = f", {im.width}×{im.height} px"
        readme.append(f"- `{path.relative_to(PACK).as_posix()}`: {size / 1024:.0f} KB{detail}")
    readme += ["", f"Total: {total / 1024 / 1024:.1f} MB.", ""]
    (PACK / "LEIA-ME.md").write_text("\n".join(readme), encoding="utf-8")
    for path in sorted(p for p in PACK.rglob("*") if p.is_file()):
        print(f"{path.relative_to(PACK).as_posix():60s} {path.stat().st_size:9d} B")
    print(f"total {sum(p.stat().st_size for p in PACK.rglob('*') if p.is_file())} B")


if __name__ == "__main__":
    main()
