import hashlib
import io
import json
import shutil
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from cycler import cycler
from matplotlib import patches
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter, MaxNLocator
from PIL import Image, ImageDraw
from scipy import stats
from torchvision import transforms

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import fruit_analytics as FA
from belt import stats as BS
from belt.classify import CropClassifier
from test_fruit_analytics import expand, gauss_events, trend_events, week

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "figures" / "out"
PUBLISH = len(sys.argv) == 1
PUBLIC = ROOT / "frontend" / "public" / "figures"
CAPTIONS = json.loads((ROOT / "figures" / "captions.json").read_text(encoding="utf-8"))
MODEL_NAME = "belt_v2"
EVAL = json.loads((ROOT / "models" / f"{MODEL_NAME}_eval.json").read_text(encoding="utf-8"))
BELT = json.loads((ROOT / "figures" / "data" / "belt_eval.json").read_text(encoding="utf-8"))
CATALOG = json.loads((ROOT / "media_src" / "catalog.json").read_text(encoding="utf-8"))
OI = {"orange": "#E69F00", "sky": "#56B4E9", "green": "#2FBF8F", "yellow": "#F0E442", "blue": "#56B4E9", "vermillion": "#E8742A", "purple": "#CC79A7", "black": "#000000"}
GOOD, POOR, ROTTEN, REVIEW = "#2FBF8F", "#E6B13C", "#E8742A", "#CC79A7"
BG, PANEL = "#1a2c25", "#213830"
INK, MUTED, LIGHT = "#e4eee8", "#a3b8ac", "#2f4c40"
CLASSES = ["boa", "baixa_qualidade", "podre"]
NAMES = {"boa": "boa", "baixa_qualidade": "baixa qualidade", "podre": "podre"}
TONES = {"boa": GOOD, "baixa_qualidade": POOR, "podre": ROTTEN}
CMAP = LinearSegmentedColormap.from_list("fruitcam", [PANEL, "#1f5a4a", "#2FBF8F", "#c9f2df"])
MM = 1 / 25.4
WIDTH = 183 * MM
BAND = 4.5
WEB_WIDTH = 1600
LABELS = {
    "synthetic": "DADOS SINTÉTICOS · resposta conhecida",
    "real": "MEDIÇÃO REAL · validação, não é teste independente",
    "schematic": "ESQUEMA · sem dados",
    "example": "EXEMPLOS REAIS · não é métrica",
    "test": "MEDIÇÃO REAL · teste com fotos de campo, não de esteira",
    "simulation": "SIMULAÇÃO · esteira sintética com recortes reais de teste",
}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 7.5,
    "axes.titlesize": 7.2,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.labelsize": 7.5,
    "xtick.labelsize": 6.8,
    "ytick.labelsize": 6.8,
    "legend.fontsize": 6.4,
    "legend.frameon": True,
    "legend.framealpha": 0.88,
    "legend.facecolor": BG,
    "legend.edgecolor": "none",
    "legend.fancybox": False,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "xtick.major.size": 2.5,
    "ytick.major.size": 2.5,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelcolor": INK,
    "ytick.labelcolor": INK,
    "text.color": INK,
    "hatch.color": MUTED,
    "lines.linewidth": 1.2,
    "axes.prop_cycle": cycler(color=[OI["blue"], OI["vermillion"], OI["green"], OI["orange"], OI["purple"], OI["sky"]]),
    "figure.facecolor": BG,
    "axes.facecolor": BG,
    "savefig.facecolor": BG,
    "svg.fonttype": "path",
    "svg.hashsalt": "fruitcam-figures",
})


def br(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def pct(x, d=0):
    return f"{100 * x:.{d}f}%".replace(".", ",")


def pval(p):
    return "p < 0,001" if p < 0.001 else f"p = {br(p, 3)}"


PCT = FuncFormatter(lambda v, _: pct(v).replace("-", "−"))
DEC = FuncFormatter(lambda v, _: f"{v:g}".replace(".", ",").replace("-", "−"))


def wilson(k, n):
    k, n = np.asarray(k, float), np.asarray(n, float)
    z = 1.959964
    p = np.where(n > 0, k / np.maximum(n, 1), np.nan)
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def figure(height):
    fig = plt.figure(figsize=(WIDTH, height * MM), layout="constrained")
    fig.get_layout_engine().set(rect=(0, BAND / height, 1, 1 - BAND / height), wspace=0.03, hspace=0.04)
    return fig


def letter(ax, s):
    ax.annotate(s, xy=(0, 1), xycoords="axes fraction", xytext=(-5, plt.rcParams["axes.titlepad"]), textcoords="offset points", ha="right", va="baseline", fontsize=9.5, fontweight="bold")


def frame(ax):
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color(MUTED)
        spine.set_linewidth(0.5)


def stamp(fig, kind):
    fig.text(0.995, 0.008, LABELS[kind], ha="right", va="bottom", fontsize=6.2, color=MUTED, fontweight="bold", gid=f"{kind}-label")


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.svg", dpi=150, metadata={"Date": None})
    fig.savefig(OUT / f"{name}.png", dpi=300, metadata={"Software": None})
    size = fig.get_size_inches()
    plt.close(fig)
    return {"width": round(size[0] * 96), "height": round(size[1] * 96)}


def fig_pipeline():
    unit = WIDTH / 100
    height = 46 * unit + BAND * MM
    fig = plt.figure(figsize=(WIDTH, height))
    ax = fig.add_axes([0, BAND * MM / height, 1, 46 * unit / height])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 46)
    ax.axis("off")
    w, h, g = 20.2, 13, 5.07
    col = [2 + i * (w + g) for i in range(4)]
    top, bottom = 27, 4
    steps = [
        (col[0], top, "Câmera", "RTSP ou USB, ~25 quadros/s", "luz constante, px/mm calibrado", False),
        (col[1], top, "Segmentação", "cor Lab contra a esteira", "área da máscara → mm", False),
        (col[2], top, "Rastreamento", "prevê a posição seguinte", "conta 1 vez na linha", False),
        (col[3], top, "Classificador", "MobileNetV3-Small, 128 px", "média de até 6 vistas", True),
        (col[3], bottom, "Decisão", "confiança < limiar → revisar", "regra de calibre opcional", False),
        (col[2], bottom, "Registro", "1 linha por fruta", "hora, câmera, lote, classe, mm", False),
        (col[1], bottom, "Estatística", "frutas/min, IC 95%", "carta p′, aceite de lote", False),
    ]
    for i, (x, y, name, l1, l2, ai) in enumerate(steps, start=1):
        edge = OI["blue"] if ai else MUTED
        ax.add_patch(patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.6", facecolor="#163447" if ai else PANEL, edgecolor=edge, linewidth=1.6 if ai else 0.8))
        ax.add_patch(patches.Circle((x + 2.6, y + h - 2.6), 1.7, facecolor=OI["blue"] if ai else "#9ad9b3", edgecolor="none"))
        ax.text(x + 2.6, y + h - 2.65, str(i), ha="center", va="center", color=BG, fontsize=6.5, fontweight="bold")
        ax.text(x + 5.2, y + h - 2.6, name, ha="left", va="center", fontsize=7.8, fontweight="bold")
        ax.text(x + 1.4, y + 5.6, l1, ha="left", va="center", fontsize=6.2)
        ax.text(x + 1.4, y + 2.6, l2, ha="left", va="center", fontsize=6.0, color=MUTED)
        if ai:
            ax.text(x + w - 1.4, y + h - 2.6, "IA", ha="right", va="center", fontsize=6.5, fontweight="bold", color=OI["blue"])
    upper, lower = top + h / 2, bottom + h / 2
    arrows = [
        ((col[0] + w, upper), (col[1], upper), "quadro\nde vídeo"),
        ((col[1] + w, upper), (col[2], upper), "caixas,\nmáscaras"),
        ((col[2] + w, upper), (col[3], upper), "recortes\nda fruta"),
        ((col[3] + w / 2, top), (col[3] + w / 2, bottom + h), "probabilidades\nmédias"),
        ((col[3], lower), (col[2] + w, lower), "evento"),
        ((col[2], lower), (col[1] + w, lower), "consulta"),
    ]
    for (x0, y0), (x1, y1), label in arrows:
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops={"arrowstyle": "-|>", "color": INK, "lw": 0.8, "shrinkA": 0, "shrinkB": 0, "mutation_scale": 7})
        if x0 == x1:
            ax.text(x0 - 1.2, (y0 + y1) / 2, label, ha="right", va="center", fontsize=5.6, color=MUTED, linespacing=1.1)
        else:
            ax.text((x0 + x1) / 2, y0 + 1, label, ha="center", va="bottom", fontsize=5.6, color=MUTED, linespacing=1.1)
    ax.add_patch(patches.FancyBboxPatch((2, 11), 3.2, 2.2, boxstyle="round,pad=0,rounding_size=0.5", facecolor="#163447", edgecolor=OI["blue"], linewidth=1.2))
    ax.text(6.2, 12.1, "aprendida (IA)", va="center", fontsize=6.3)
    ax.add_patch(patches.FancyBboxPatch((2, 6.5), 3.2, 2.2, boxstyle="round,pad=0,rounding_size=0.5", facecolor=PANEL, edgecolor=MUTED, linewidth=0.8))
    ax.text(6.2, 7.6, "código determinístico, testado", va="center", fontsize=6.3)
    ax.text(2, 45, "Uma decisão por fruta · classes: boa, baixa qualidade (imatura), podre · castanha e melão sem fotos de treino", fontsize=6.3, color=MUTED, va="top")
    stamp(fig, "schematic")
    return save(fig, "fig1-pipeline")


def model_view(classifier, image):
    size = classifier.size
    tf = transforms.Compose([transforms.Resize((size, size)), transforms.ToTensor(), transforms.Normalize(mean=list(classifier.mean), std=list(classifier.std))])
    model = classifier.model
    x = tf(image).unsqueeze(0)
    store = {}

    def hook(module, inputs, output):
        output.retain_grad()
        store["a"] = output

    handle = model.features[-1].register_forward_hook(hook)
    logits = model(x)
    handle.remove()
    probs = torch.softmax(logits / classifier.temperature, dim=1)[0].detach().numpy()
    k = int(probs.argmax())
    model.zero_grad()
    logits[0, k].backward()
    a = store["a"][0].detach()
    g = store["a"].grad[0]
    cam = torch.relu((g.mean(dim=(1, 2))[:, None, None] * a).sum(0))
    cam = cam / cam.max() if cam.max() > 0 else cam
    cam = torch.nn.functional.interpolate(cam[None, None], size=(size, size), mode="bilinear", align_corners=False)[0, 0].numpy()
    shown = x[0].numpy().transpose(1, 2, 0) * classifier.std + classifier.mean
    return probs, k, cam, np.clip(shown, 0, 1)


def fig_classification():
    classifier = CropClassifier(ROOT / "models" / f"{MODEL_NAME}.pt")
    photo = Image.open(ROOT / "media_src" / "commons" / "caju-vermelho.jpg").convert("RGB")
    fx0, fy0, fx1, fy1 = CATALOG["variants"]["fruta-caju"]["crop"]
    box = (round(fx0 * photo.width), round(fy0 * photo.height), round(fx1 * photo.width), round(fy1 * photo.height))
    crop = photo.crop(box)
    probs, k, cam, shown = model_view(classifier, crop)
    direct = classifier.probs([np.asarray(crop)[:, :, ::-1].copy()])[0]
    assert np.allclose(direct, probs, atol=2e-3), (direct, probs)
    synth = Image.new("RGB", (320, 240), (245, 243, 236))
    ImageDraw.Draw(synth).ellipse([80, 60, 240, 180], fill=(70, 45, 25))
    s_probs, s_k, _, _ = model_view(classifier, synth)
    fig = figure(128)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.3, 1.0], height_ratios=[1.0, 0.8])
    ax = fig.add_subplot(gs[0, 0])
    scale = 1200 / photo.width
    small = photo.resize((1200, round(photo.height * scale)), Image.LANCZOS)
    ax.imshow(small)
    x0, y0, x1, y1 = (v * scale - 0.5 for v in box)
    ax.add_patch(patches.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, edgecolor=OI["yellow"], linewidth=2.2))
    ax.text(x0 + 10, y1 - 14, "recorte da fruta", color="black", fontsize=6.4, va="bottom", backgroundcolor=OI["yellow"])
    bar = 500 * scale
    ax.plot([small.width - 30 - bar, small.width - 30], [small.height - 36] * 2, color="white", linewidth=2.4, solid_capstyle="butt")
    ax.text(small.width - 30 - bar / 2, small.height - 50, "500 px", color="white", ha="center", va="bottom", fontsize=6.4, fontweight="bold")
    ax.set_xlim(-0.5, small.width - 0.5)
    ax.set_ylim(small.height - 0.5, -0.5)
    frame(ax)
    ax.set_title(f"foto real ({photo.width}×{photo.height} px) e o recorte classificado")
    letter(ax, "a")
    ax = fig.add_subplot(gs[0, 1])
    ax.imshow(shown)
    heat = ax.imshow(cam, cmap="cividis", alpha=0.5, vmin=0, vmax=1)
    frame(ax)
    ax.set_title(f"entrada do modelo ({classifier.size}×{classifier.size} px) + Grad-CAM")
    cb = fig.colorbar(heat, ax=ax, fraction=0.05, pad=0.03, ticks=[0, 1])
    cb.ax.set_yticklabels(["0", "máx."])
    cb.set_label("Grad-CAM, relativo ao máximo", fontsize=6.4)
    cb.ax.tick_params(labelsize=6.4)
    cb.outline.set_linewidth(0.5)
    letter(ax, "b")
    ax = fig.add_subplot(gs[1, 0])
    inputs = [("recorte da foto (a)", probs), ("elipse sintética (d)", s_probs)]
    xs = np.arange(len(inputs))
    for j, name in enumerate(CLASSES):
        values = [pr[classifier.classes.index(name)] for _, pr in inputs]
        bars = ax.bar(xs + (j - 1) * 0.26, values, width=0.24, color=TONES[name], label=NAMES[name])
        for b, v in zip(bars, values):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.015, br(v, 2), ha="center", va="bottom", fontsize=5.8)
    ax.set_xticks(xs, [name for name, _ in inputs])
    ax.set_xlim(-0.6, 1.6)
    ax.set_ylim(0, 1.18)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1])
    ax.yaxis.set_major_formatter(DEC)
    ax.set_ylabel("probabilidade calibrada")
    ax.set_xlabel("entrada")
    ax.legend(loc="upper center", ncol=3)
    ax.set_title("saída real do modelo para cada entrada")
    letter(ax, "c")
    ax = fig.add_subplot(gs[1, 1])
    ax.imshow(synth)
    frame(ax)
    s_label = classifier.classes[s_k]
    ax.text(160, 228, f"saída real: {NAMES.get(s_label, s_label)}, {br(float(s_probs[s_k]), 2)}", ha="center", va="bottom", fontsize=6.4, color="black")
    ax.set_title("elipse sintética, fora do treino")
    letter(ax, "d")
    stamp(fig, "example")
    meta = save(fig, "fig2-classificacao")
    label = classifier.classes[k]
    meta["outputs"] = {"crop": {"label": label, "confidence": float(probs[k]), "box": list(box), "probs": dict(zip(classifier.classes, map(float, probs)))}, "synthetic": {"label": s_label, "confidence": float(s_probs[s_k])}}
    return meta


def sector_events():
    rng = np.random.default_rng(3)
    spec = []
    for w in range(10):
        total = int(rng.poisson(60))
        rotten = int(rng.binomial(total, float(np.clip(rng.normal(0.20, 0.05), 0, 1))))
        spec += [(week(w), 7, "norte", "caju", "podre", rotten), (week(w), 7, "norte", "caju", "nao_podre", total - rotten)]
    return FA.to_events(expand(spec, rng)).sort_values("timestamp").reset_index(drop=True)


def fig_events():
    events = sector_events()
    counts = FA.counts(events, "week")
    labels = [p.start_time.strftime("%d/%m") for p in counts.index]
    n = (counts["good"] + counts["rotten"]).to_numpy()
    rate = counts["rotten"].to_numpy() / n
    lo, hi = wilson(counts["rotten"].to_numpy(), n)
    fig = figure(64)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.4, 1.0, 1.0])
    ax = fig.add_subplot(gs[0])
    ax.set_axis_off()
    rows = [[r.timestamp.strftime("%d/%m %H:%M"), r.sector, r.fruit_type, "sim" if r.is_good else "não", r.deformity_type if isinstance(r.deformity_type, str) else "—"] for r in events.head(7).itertuples()]
    table = ax.table(cellText=rows, colLabels=["data e hora", "setor", "fruta", "boa?", "defeito"], cellLoc="left", colLoc="left", colWidths=[0.31, 0.17, 0.16, 0.14, 0.22], bbox=[0, 0.16, 1, 0.84])
    table.auto_set_font_size(False)
    table.set_fontsize(6.3)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor(LIGHT if r else INK)
        cell.set_linewidth(0.5)
        if r == 0:
            cell.set_text_props(fontweight="bold")
    ax.text(0, 0.04, f"… mais {len(events) - 7} linhas (n = {len(events)} eventos, 1 setor)", fontsize=6.3, color=MUTED, transform=ax.transAxes)
    ax.set_title("eventos: uma linha por foto")
    letter(ax, "a")
    ax = fig.add_subplot(gs[1])
    x = np.arange(len(labels))
    ax.bar(x, counts["good"], color=GOOD, width=0.72, label="boas")
    ax.bar(x, counts["rotten"], bottom=counts["good"], color=ROTTEN, width=0.72, label="podres")
    for xi, total in zip(x, n):
        ax.text(xi, total + 1, str(int(total)), ha="center", va="bottom", fontsize=5.6, color=MUTED)
    ax.set_xticks(x[::2], labels[::2])
    ax.set_ylabel("frutas por semana")
    ax.set_xlabel("semana (início)")
    ax.set_ylim(0, n.max() * 1.45)
    ax.legend(loc="upper left", ncol=2, handlelength=1.2, columnspacing=1.0)
    ax.set_title("contagem semanal")
    letter(ax, "b")
    ax = fig.add_subplot(gs[2])
    overall = counts["rotten"].sum() / n.sum()
    ax.axhline(overall, color=MUTED, linestyle=(0, (4, 3)), linewidth=0.8, label=f"período inteiro: {pct(overall, 1)}")
    ax.errorbar(x, rate, yerr=[rate - lo, hi - rate], fmt="o", color=ROTTEN, markersize=3.2, elinewidth=0.9, capsize=1.6, label="semana (IC 95%)")
    ax.set_xticks(x[::2], labels[::2])
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylim(0, max(hi.max() * 1.4, 0.5))
    ax.set_ylabel("proporção de podres")
    ax.set_xlabel("semana (início)")
    ax.legend(loc="upper left", handlelength=1.6)
    ax.set_title("proporção de podres")
    letter(ax, "c")
    stamp(fig, "synthetic")
    return save(fig, "fig3-evento-estatistica")


def forecast_panel(ax, y, nw, truth, note):
    t = np.arange(len(y))
    k = np.round(y * nw)
    lo, hi = wilson(k, nw)
    mean, se, dof, slope, intercept = FA.linear_fit(t, y, len(y))
    q = stats.t.ppf(0.975, dof)
    grid = np.linspace(0, len(y), 200)
    tm = t.mean()
    sxx = ((t - tm) ** 2).sum()
    s = np.sqrt(((y - intercept - slope * t) ** 2).sum() / dof)
    band = q * s * np.sqrt(1 + 1 / len(y) + (grid - tm) ** 2 / sxx)
    fit = intercept + slope * grid
    ax.fill_between(grid, fit - band, fit + band, color=OI["sky"], alpha=0.25, linewidth=0, label="intervalo de previsão 95%")
    ax.plot(grid, fit, color=OI["blue"], linewidth=1.1, label="reta ajustada")
    ax.errorbar(t, y, yerr=[y - lo, hi - y], fmt="o", color=ROTTEN, markersize=2.6, elinewidth=0.7, capsize=0, label="semana observada (IC 95%)")
    ax.errorbar([len(y)], [mean], yerr=[[q * se], [q * se]], fmt="s", color=INK, markersize=3.4, elinewidth=1.2, capsize=2.5, label="previsão da próxima semana")
    ax.plot([len(y)], [truth], marker="D", color=OI["orange"], markersize=4.2, linestyle="none", markeredgecolor=INK, markeredgewidth=0.5, label="valor verdadeiro")
    ax.axhline(0.5, color=MUTED, linestyle=(0, (4, 3)), linewidth=0.7)
    ax.yaxis.set_major_formatter(PCT)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylim(0, 1)
    ax.set_xlabel("semana")
    ax.set_ylabel("proporção de podres")
    p = FA.p_above_half(mean, se, dof)
    p_text = "> 99%" if p > 0.99 else "< 1%" if p < 0.01 else pct(p)
    ax.text(0.03, 0.97, f"n = {len(y)} semanas × {int(nw[0])} frutas\nP(mais podres que boas): {p_text}\n{note}", transform=ax.transAxes, va="top", fontsize=6.1, linespacing=1.3)
    return mean, q * se


def fig_forecast():
    fig = figure(66)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.2, 1.0, 1.0])
    props, n = FA.sector_proportions(trend_events(0), "week")
    ax = fig.add_subplot(gs[0])
    forecast_panel(ax, props["rising"].to_numpy(), n["rising"].to_numpy(), 0.20 + 0.019 * 30, "passa nos critérios do painel")
    found = dict(zip(*reversed(ax.get_legend_handles_labels())))
    order = ["semana observada (IC 95%)", "reta ajustada", "intervalo de previsão 95%", "previsão da próxima semana", "valor verdadeiro"]
    fig.legend([found[k] for k in order], order, loc="outside upper left", ncol=3, fontsize=6.2, handlelength=1.6, columnspacing=1.4)
    ax.set_title("série longa, tendência conhecida")
    letter(ax, "a")
    props_s, n_s = FA.sector_proportions(trend_events(1, weeks=10, n=60), "week")
    ax = fig.add_subplot(gs[1])
    forecast_panel(ax, props_s["rising"].to_numpy(), n_s["rising"].to_numpy(), 0.20 + 0.019 * 10, "não confiável: < 20 semanas")
    ax.set_title("série curta, mesma tendência")
    letter(ax, "b")
    coverage = []
    for seed in range(1, 11):
        props_c, _ = FA.sector_proportions(trend_events(seed), "week")
        for sector in ("rising", "flat"):
            v = props_c[sector].to_numpy()
            coverage.append(FA.backtest(np.arange(len(v)), v, FA.MIN_PERIODS)["bt_coverage"])
    origins = 30 - FA.MIN_PERIODS
    band = stats.binom.ppf([0.025, 0.975], origins, 0.95) / origins
    ax = fig.add_subplot(gs[2])
    ax.axhspan(band[0], band[1], color=LIGHT, linewidth=0, label="faixa esperada (cobertura real 95%)")
    ax.axhline(0.95, color=MUTED, linestyle=(0, (4, 3)), linewidth=0.8, label="nominal: 95%")
    ax.plot(np.arange(1, len(coverage) + 1), coverage, "o", color=OI["blue"], markersize=3.2, label=f"série simulada ({origins} previsões)")
    ax.axhline(np.mean(coverage), color=OI["blue"], linewidth=1.0, label=f"média: {pct(np.mean(coverage), 1)}")
    ax.yaxis.set_major_formatter(PCT)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylim(0.5, 1.02)
    ax.set_xlabel("série simulada")
    ax.set_ylabel("cobertura do intervalo de 95%")
    ax.set_title(f"cobertura retroativa, {len(coverage)} séries")
    ax.legend(loc="lower left", fontsize=5.9, handlelength=1.4)
    letter(ax, "c")
    stamp(fig, "synthetic")
    meta = save(fig, "fig4-previsao")
    meta["coverage_mean"] = float(np.mean(coverage))
    return meta


def gaussian_row(fig, gs, row, x, name, letters, rng):
    mean, sd, n = x.mean(), x.std(ddof=1), len(x)
    w, p = stats.shapiro(x)
    ax = fig.add_subplot(gs[row, 0])
    lo_x, hi_x = min(x.min(), mean - 3.5 * sd), max(x.max(), mean + 5 * sd)
    ax.axvspan(mean - 2 * sd, mean + 2 * sd, color=OI["blue"], alpha=0.08, linewidth=0, label="±2σ")
    ax.axvspan(mean - sd, mean + sd, color=OI["blue"], alpha=0.14, linewidth=0, label="±1σ")
    if lo_x < 0:
        ax.axvspan(lo_x, 0, facecolor="none", edgecolor=MUTED, hatch="////", linewidth=0, label="impossível (< 0%)")
    ax.hist(x, bins="auto", density=True, color=OI["sky"], alpha=0.75, edgecolor=BG, linewidth=0.4, label=f"semanas (n = {n})")
    grid = np.linspace(lo_x, hi_x, 300)
    flagged = p < FA.ALPHA or (stats.norm.cdf(0, mean, sd) + stats.norm.sf(1, mean, sd)) > FA.MAX_OUTSIDE
    ax.plot(grid, stats.norm.pdf(grid, mean, sd), color=MUTED if flagged else ROTTEN, linestyle=(0, (4, 3)) if flagged else "-", linewidth=1.2, label="normal ajustada")
    ax.axvline(mean, color=INK, linewidth=0.9, label="média")
    ax.xaxis.set_major_formatter(PCT)
    ax.set_xlim(lo_x, hi_x)
    ax.set_xlabel("proporção semanal de podres")
    ax.set_ylabel("densidade")
    ax.set_title(f"{name}: média {pct(mean, 1)}, σ {pct(sd, 1)}")
    ax.legend(loc="upper right", fontsize=5.9, handlelength=1.2)
    letter(ax, letters[0])
    ax = fig.add_subplot(gs[row, 1])
    (osm, osr), _ = stats.probplot(x, dist="norm")
    sims = np.sort(rng.normal(mean, sd, (2000, n)), axis=1)
    env_lo, env_hi = np.percentile(sims, [2.5, 97.5], axis=0)
    ax.fill_between(osm, env_lo, env_hi, color=LIGHT, linewidth=0, label="envelope 95% (2000 simulações)")
    ax.plot(osm, mean + sd * osm, color=INK, linewidth=0.9, label="normal perfeita")
    outside = (osr < env_lo) | (osr > env_hi)
    ax.plot(osm[~outside], osr[~outside], "o", color=OI["blue"], markersize=2.3, label="dentro do envelope")
    if outside.any():
        ax.plot(osm[outside], osr[outside], "o", color=ROTTEN, markersize=2.6, label=f"fora do envelope ({int(outside.sum())})")
    ax.yaxis.set_major_formatter(PCT)
    ax.set_xlabel("quantil teórico da normal padrão")
    ax.set_ylabel("quantil observado")
    ax.set_title("gráfico Q-Q com envelope de 95%")
    verdict = "ajuste ruim" if flagged else "sem alerta (não prova normalidade)"
    ax.text(0.97, 0.04, f"Shapiro-Wilk: W = {br(w, 3)}, {pval(p)}\n{verdict}", transform=ax.transAxes, ha="right", va="bottom", fontsize=6.3, color=ROTTEN if flagged else INK, fontweight="bold" if flagged else "normal", linespacing=1.3)
    ax.legend(loc="upper left", fontsize=5.9, handlelength=1.2)
    letter(ax, letters[1])
    return {"n": n, "mean": float(mean), "std": float(sd), "shapiro_w": float(w), "shapiro_p": float(p), "flagged": bool(flagged), "outside_envelope": int(outside.sum())}


def fig_gaussian():
    props, _ = FA.sector_proportions(gauss_events(0, n=200), "week")
    rng = np.random.default_rng(0)
    fig = figure(116)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.1, 1.0])
    a = gaussian_row(fig, gs, 0, props["A"].dropna().to_numpy(), "setor gerado como normal", ("a", "b"), rng)
    c = gaussian_row(fig, gs, 1, props["C"].dropna().to_numpy(), "setor assimétrico", ("c", "d"), rng)
    stamp(fig, "synthetic")
    meta = save(fig, "fig5-gaussiana")
    meta["sectors"] = {"normal": a, "skewed": c}
    return meta


def matrix(ax, confusion, title):
    cm = np.array(confusion, float)
    share = cm / cm.sum(axis=1, keepdims=True)
    ax.imshow(share, cmap=CMAP, vmin=0, vmax=1)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f"{int(cm[i, j])}\n{pct(share[i, j])}", ha="center", va="center", fontsize=6.3, color=BG if share[i, j] > 0.6 else INK, linespacing=1.2)
    ticks = ["boa", "baixa\nqual.", "podre"]
    ax.set_xticks(range(3), ticks)
    ax.set_yticks(range(3), ticks)
    ax.set_xlabel("previsto")
    ax.set_ylabel("verdadeiro")
    ax.spines[:].set_visible(False)
    ax.tick_params(length=0)
    ax.set_title(title)


def fig_quality():
    test = EVAL["test"]
    y = np.array(EVAL["test_predictions"]["y"])
    p = np.array(EVAL["test_predictions"]["p"])
    fig = figure(124)
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.0])
    ax = fig.add_subplot(gs[0, 0])
    matrix(ax, test["confusion"], f"teste: n = {test['n']} recortes de {test['photos']} fotos")
    letter(ax, "a")
    ax = fig.add_subplot(gs[0, 1])
    for j, c in enumerate(CLASSES):
        d = test["per_class"][c]
        for dx, key, marker in ((-0.12, "recall", "o"), (0.12, "precision", "s")):
            v = d[key]
            lo, hi = d[f"{key}_ci95"]
            ax.errorbar([j + dx], [v], yerr=[[v - lo], [hi - v]], fmt=marker, color=TONES[c], markersize=3.6, elinewidth=1.0, capsize=2.0, markerfacecolor=TONES[c] if key == "recall" else BG)
    acc, (alo, ahi) = test["accuracy"], test["accuracy_ci95_cluster_bootstrap"]
    ax.errorbar([3], [acc], yerr=[[acc - alo], [ahi - acc]], fmt="D", color=INK, markersize=3.8, elinewidth=1.0, capsize=2.0)
    majority = CLASSES[int(np.argmax([sum(r) for r in test["confusion"]]))]
    ax.plot([2.8, 3.2], [test["majority_baseline_accuracy"]] * 2, color=MUTED, linewidth=2.4, solid_capstyle="butt")
    ax.text(3.24, test["majority_baseline_accuracy"], "palpite\n“sempre " + {"boa": "boa", "baixa_qualidade": "baixa\nqualidade", "podre": "podre"}[majority] + "”", fontsize=5.6, color=MUTED, va="center")
    ax.plot([], [], "o", color=MUTED, label="sensibilidade (recall)")
    ax.plot([], [], "s", color=MUTED, markerfacecolor=BG, label="precisão")
    ax.set_xticks(range(4), ["boa", "baixa\nqualidade", "podre", "acurácia"])
    ax.set_xlim(-0.5, 4.0)
    lows = [test["per_class"][c][f"{k}_ci95"][0] for c in CLASSES for k in ("recall", "precision")] + [alo]
    ax.set_ylim(max(0.0, np.floor((min(lows) - 0.05) * 10) / 10), 1.02)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylabel("valor (IC 95%)")
    ax.legend(loc="upper left")
    ax.set_title("por classe (Wilson) e acurácia (bootstrap por foto)")
    letter(ax, "b")
    ax = fig.add_subplot(gs[1, 0])
    conf, pred = p.max(1), p.argmax(1)
    edges = np.linspace(1 / 3, 1, 9)
    centers, accs, los, his, ns = [], [], [], [], []
    for lo_e, hi_e in zip(edges[:-1], edges[1:]):
        m = (conf > lo_e) & (conf <= hi_e)
        if m.sum() < 5:
            continue
        k = int((pred[m] == y[m]).sum())
        lo, hi = wilson(k, m.sum())
        centers.append(conf[m].mean())
        accs.append(k / m.sum())
        los.append(float(lo))
        his.append(float(hi))
        ns.append(int(m.sum()))
    centers, accs = np.array(centers), np.array(accs)
    ax.plot([1 / 3, 1], [1 / 3, 1], color=MUTED, linestyle=(0, (4, 3)), linewidth=0.8, label="calibração perfeita")
    ax.errorbar(centers, accs, yerr=[accs - np.array(los), np.array(his) - accs], fmt="o-", color=OI["blue"], markersize=3.4, elinewidth=1.0, capsize=2.0, linewidth=0.9, label="modelo calibrado (IC 95%)")
    for cx, n in zip(centers, ns):
        ax.text(cx, 0.06, str(n), ha="center", va="bottom", fontsize=5.8, color=MUTED)
    ax.text(0.34, 0.12, "n por faixa:", fontsize=5.8, color=MUTED, va="bottom")
    ax.xaxis.set_major_formatter(PCT)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_xlim(0.3, 1.02)
    ax.set_ylim(0, 1.04)
    ax.set_xlabel("confiança média da faixa")
    ax.set_ylabel("acerto na faixa")
    ax.set_title(f"confiabilidade: ECE {br(EVAL['test_uncalibrated_ece'], 3)} → {br(test['ece'], 3)} (temperatura {br(EVAL['model']['temperature'], 2)})")
    ax.legend(loc="upper left")
    letter(ax, "c")
    ax = fig.add_subplot(gs[1, 1])
    order = np.argsort(-conf)
    hits = (pred[order] == y[order]).astype(float)
    coverage = np.arange(1, len(hits) + 1) / len(hits)
    running = np.cumsum(hits) / np.arange(1, len(hits) + 1)
    ax.plot(coverage, running, color=OI["blue"], linewidth=1.3, label="decide só as mais confiantes")
    ax.axhline(test["accuracy"], color=MUTED, linestyle=(0, (4, 3)), linewidth=0.8, label=f"decide todas: {pct(test['accuracy'], 1)}")
    rej = test["with_reject"]
    if rej["threshold"] is not None:
        ax.plot([rej["coverage"]], [rej["accuracy_on_accepted"]], "D", color=OI["orange"], markersize=5, markeredgecolor=BG, label=f"limiar {br(rej['threshold'], 2)} (escolhido na validação)")
        ax.annotate(f"{pct(rej['coverage'])} decididas\n{pct(rej['accuracy_on_accepted'], 1)} de acerto", xy=(rej["coverage"], rej["accuracy_on_accepted"]), xytext=(10, -26), textcoords="offset points", fontsize=6.0, color=INK)
    else:
        ax.text(0.97, 0.97, "nenhum limiar atinge 95% de acerto\nna validação: todas as frutas\nvão para revisão manual", transform=ax.transAxes, ha="right", va="top", fontsize=6.0, color=OI["orange"])
    floor = max(0.0, np.floor((min(running[len(running) // 20:].min(), test["accuracy"]) - 0.05) * 10) / 10)
    ax.xaxis.set_major_formatter(PCT)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_xlim(0, 1.02)
    ax.set_ylim(floor, 1.01)
    ax.set_xlabel("fração decidida automaticamente (o resto vai para revisão)")
    ax.set_ylabel("acerto entre as decididas")
    ax.set_title("cobertura × acerto com revisão manual")
    ax.legend(loc="lower left")
    letter(ax, "d")
    stamp(fig, "test")
    return save(fig, "fig6-qualidade")


def line_events(seed=4, hours=8, rate=2.0, shift_lot=3, lot_minutes=90):
    rng = np.random.default_rng(seed)
    start = np.datetime64("2026-10-01T06:00")
    rows = []
    for minute in range(int(hours * 60)):
        lot = minute // lot_minutes + 1
        mix = np.array([0.45, 0.2, 0.35]) if lot == shift_lot else np.array([0.62, 0.24, 0.14])
        n = rng.poisson(rate * 60)
        for second, k in zip(np.sort(rng.uniform(0, 60, n)), rng.choice(3, size=n, p=mix)):
            rows.append((start + np.timedelta64(minute * 60_000 + int(second * 1000), "ms"), CLASSES[k], bool(rng.random() < 0.03), f"L-{lot:02d}"))
    df = pd.DataFrame(rows, columns=["timestamp", "label", "needs_review", "lot"])
    return df, pd.Timestamp(start), pd.Timestamp(start) + pd.Timedelta(hours=hours)


def fig_line():
    df, start, end = line_events()
    spec = 0.18
    summary = BS.summary(df, start, end, 15, spec)
    pc = summary["p_chart"]
    x = np.arange(len(pc["p"]))
    labels = [w["start"][11:16] for w in summary["windows"]]
    fig = figure(70)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.55, 1.0])
    ax = fig.add_subplot(gs[0])
    for i, lot in enumerate(summary["lots"]):
        a = (np.datetime64(lot["first"]) - np.datetime64(start)) / np.timedelta64(15, "m")
        b = (np.datetime64(lot["last"]) - np.datetime64(start)) / np.timedelta64(15, "m")
        if i % 2:
            ax.axvspan(a - 0.5, b + 0.5, color=PANEL, linewidth=0)
        ax.text((a + b) / 2, 0.012, lot["lot"], ha="center", va="bottom", fontsize=5.8, color=MUTED)
    ax.fill_between(x, 0, pc["ucl"], step="mid", color=OI["blue"], alpha=0.12, linewidth=0, label="faixa sob controle (p′ de Laney, 3σ)")
    ax.step(x, pc["ucl"], where="mid", color=OI["blue"], linewidth=0.8)
    ax.axhline(pc["center"], color=MUTED, linestyle=(0, (4, 3)), linewidth=0.8, label=f"mediana {pct(pc['center'], 1)}")
    ax.plot(x, pc["p"], "o-", color=INK, markersize=2.6, linewidth=0.8, label="% de podres na janela de 15 min")
    alarms = sorted({a["index"] for a in pc["alarms"]})
    ax.plot(x[alarms], np.array(pc["p"])[alarms], "D", color=ROTTEN, markersize=5, markeredgecolor=BG, label=f"alarme ({len(alarms)} janelas)")
    ax.set_xticks(x[::4], labels[::4])
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylim(0, 0.5)
    ax.set_xlabel("hora (janelas completas de 15 min)")
    ax.set_ylabel("proporção de podres")
    ax.legend(loc="upper right", fontsize=5.8)
    ax.set_title("carta de controle p′, linha simulada de 8 h")
    letter(ax, "a")
    ax = fig.add_subplot(gs[1])
    colors = {"aprovado": GOOD, "reprovado": ROTTEN, "inconclusivo": POOR}
    for i, lot in enumerate(summary["lots"]):
        share, (lo, hi) = lot["rotten"]["share"], lot["rotten"]["ci95"]
        ax.errorbar([share], [i], xerr=[[share - lo], [hi - share]], fmt="o", color=colors[lot["verdict"]], markersize=4, elinewidth=1.4, capsize=2.5)
        ax.text(0.73, i, f"{lot['verdict']} · n = {lot['n']}", va="center", ha="right", fontsize=5.8, color=colors[lot["verdict"]])
    ax.axvline(spec, color=INK, linewidth=1.0, linestyle=(0, (4, 3)))
    ax.text(spec, -0.55, f" máx. {pct(spec)}", fontsize=6.0, color=INK, va="bottom")
    ax.set_yticks(range(len(summary["lots"])), [lot["lot"] for lot in summary["lots"]])
    ax.set_ylim(len(summary["lots"]) - 0.5, -0.9)
    ax.xaxis.set_major_formatter(PCT)
    ax.set_xlim(0, 0.75)
    ax.set_xticks([0, 0.2, 0.4, 0.6])
    ax.set_xlabel("% de podres no lote (IC 95% de Wilson)")
    ax.set_title("aceite de lote pelo intervalo")
    letter(ax, "b")
    stamp(fig, "synthetic")
    meta = save(fig, "fig7-linha")
    meta["line"] = {"alarm_windows": alarms, "verdicts": {lot["lot"]: lot["verdict"] for lot in summary["lots"]}, "center": pc["center"], "sigma_z": pc["sigma_z"]}
    return meta


def fig_belt():
    c = BELT["counting"]
    fig = figure(70)
    gs = fig.add_gridspec(1, 3, width_ratios=[0.8, 0.95, 1.1])
    ax = fig.add_subplot(gs[0])
    bars = [("cruza-\nram", c["fruits_that_crossed_the_line"], MUTED), ("conta-\ndas", c["counted"], OI["blue"]), ("distin-\ntas", c["distinct_true_fruits"], GOOD), ("dupli-\ncadas", c["double_counts"], ROTTEN)]
    for i, (name, v, color) in enumerate(bars):
        ax.bar(i, v, color=color, width=0.7)
        ax.text(i, v + c["counted"] * 0.015, str(v), ha="center", va="bottom", fontsize=6.4)
    ax.set_xticks(range(len(bars)), [b[0] for b in bars])
    ax.set_ylim(0, c["counted"] * 1.15)
    ax.set_ylabel("frutas")
    ax.set_title(f"contagem em {BELT['setup']['minutes_simulated']} min simulados")
    letter(ax, "a")
    ax = fig.add_subplot(gs[1])
    matrix(ax, BELT["multi_view"]["confusion"], f"classificação na esteira (n = {BELT['multi_view']['n']})")
    letter(ax, "b")
    ax = fig.add_subplot(gs[2])
    rows = [("1 vista", BELT["single_view"]), (f"média de\n{BELT['views_per_fruit']:.0f} vistas", BELT["multi_view"])]
    for i, (name, m) in enumerate(rows):
        lo, hi = m["accuracy_ci95"]
        ax.errorbar([i], [m["accuracy"]], yerr=[[m["accuracy"] - lo], [hi - m["accuracy"]]], fmt="o", color=OI["blue"], markersize=4, elinewidth=1.2, capsize=2.5)
        ax.text(i + 0.08, m["accuracy"], pct(m["accuracy"], 1), fontsize=6.0, va="center")
    rv = BELT["with_review"]
    lows = [m["accuracy_ci95"][0] for _, m in rows]
    if rv["n_decided"]:
        k = round(rv["accuracy_on_decided"] * rv["n_decided"])
        lo, hi = wilson(k, rv["n_decided"])
        lows.append(lo)
        ax.errorbar([2], [rv["accuracy_on_decided"]], yerr=[[rv["accuracy_on_decided"] - lo], [hi - rv["accuracy_on_decided"]]], fmt="D", color=OI["orange"], markersize=4, elinewidth=1.2, capsize=2.5)
        ax.text(2.08, rv["accuracy_on_decided"], f"{pct(rv['accuracy_on_decided'], 1)}\n({pct(rv['coverage'])} decididas)", fontsize=6.0, va="center")
    else:
        ax.text(2, 0.5, "nenhuma\ndecidida:\ntudo para\nrevisão", ha="center", va="center", fontsize=6.0, color=OI["orange"], transform=ax.get_xaxis_transform())
    ax.set_xticks(range(3), [rows[0][0], rows[1][0], "com\nrevisão"])
    ax.set_xlim(-0.4, 2.9)
    ax.set_ylim(max(0.0, np.floor((min(lows) - 0.05) * 10) / 10), 1.02)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_ylabel("acerto (IC 95%)")
    ax.set_title("acerto ponta a ponta")
    letter(ax, "c")
    stamp(fig, "simulation")
    return save(fig, "fig8-esteira")


def publish(metas):
    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    PUBLIC.mkdir(parents=True)
    items = {}
    for name, meta in metas.items():
        cap = CAPTIONS[name]
        files = {}
        for ext in ("svg", "png"):
            data = (OUT / f"{name}.{ext}").read_bytes()
            rel = f"figures/{name}.{hashlib.sha256(data).hexdigest()[:10]}.{ext}"
            (ROOT / "frontend" / "public" / rel).write_bytes(data)
            files[ext] = rel
        files["web"] = files["svg"]
        if cap.get("raster"):
            im = Image.open(OUT / f"{name}.png").convert("RGB")
            im = im.resize((WEB_WIDTH, round(im.height * WEB_WIDTH / im.width)), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "WEBP", quality=82, method=6)
            data = buf.getvalue()
            rel = f"figures/{name}.{hashlib.sha256(data).hexdigest()[:10]}.webp"
            (ROOT / "frontend" / "public" / rel).write_bytes(data)
            files["web"] = rel
        items[name] = {
            "number": cap["number"],
            "label": cap["label"],
            "title": cap["title"],
            "alt": cap["alt"],
            "caption": cap["caption"],
            "assets": cap.get("assets", []),
            "width": meta["width"],
            "height": meta["height"],
            **files,
        }
    test = EVAL["test"]
    summary = {
        "model": {k: EVAL["model"][k] for k in ("file", "architecture", "img_size", "classes", "temperature", "reject_below")},
        "data": {k: EVAL["data"][k] for k in ("class_map", "counts", "photos", "split", "selection")},
        "test": {
            "n": test["n"], "photos": test["photos"], "accuracy": test["accuracy"], "accuracy_ci95": test["accuracy_ci95_cluster_bootstrap"],
            "balanced_accuracy": test["balanced_accuracy"], "majority_baseline_accuracy": test["majority_baseline_accuracy"],
            "recall": {c: test["per_class"][c]["recall"] for c in CLASSES}, "precision": {c: test["per_class"][c]["precision"] for c in CLASSES},
            "rotten_as_good": test["rotten_predicted_good"], "ece": test["ece"], "ece_uncalibrated": EVAL["test_uncalibrated_ece"], "with_reject": test["with_reject"],
        },
        "belt": {"counting": BELT["counting"], "multi_view": {k: BELT["multi_view"][k] for k in ("n", "accuracy", "accuracy_ci95", "balanced_accuracy")}, "single_view_accuracy": BELT["single_view"]["accuracy"], "with_review": BELT["with_review"], "size_ratio_median": BELT["size_ratio_median"]},
        "classificationExample": metas["fig2-classificacao"]["outputs"],
        "forecastCoverage": metas["fig4-previsao"]["coverage_mean"],
        "gaussian": metas["fig5-gaussiana"]["sectors"],
        "line": metas["fig7-linha"]["line"],
    }
    order = sorted(items, key=lambda k: items[k]["number"])
    (ROOT / "frontend" / "src" / "figures.json").write_text(json.dumps({"order": order, "items": items, "modelEval": summary}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main():
    metas = {
        "fig1-pipeline": fig_pipeline(),
        "fig2-classificacao": fig_classification(),
        "fig3-evento-estatistica": fig_events(),
        "fig4-previsao": fig_forecast(),
        "fig5-gaussiana": fig_gaussian(),
        "fig6-qualidade": fig_quality(),
        "fig7-linha": fig_line(),
        "fig8-esteira": fig_belt(),
    }
    if PUBLISH:
        publish(metas)
    for name in metas:
        print(f"{name:26s} svg {(OUT / f'{name}.svg').stat().st_size:8d} B  png {(OUT / f'{name}.png').stat().st_size:8d} B")


if __name__ == "__main__":
    main()
