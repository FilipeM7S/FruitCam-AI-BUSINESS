import numpy as np
import pandas as pd

from analytics import fruit_analytics as FA

DEFECTS = ("baixa_qualidade", "podre", "queimada", "quebrada")
FRUITS = ("caju", "castanha", "melao")
VOLUME = {1: 1.1, 2: 0.8, 3: 0.6, 4: 0.5, 5: 0.5, 6: 0.55, 7: 0.6, 8: 0.9, 9: 1.4, 10: 1.9, 11: 2.0, 12: 1.6}
RAINY = (2, 3, 4, 5)
HARVEST = (8, 9, 10, 11, 12, 1)
DEFECT_MIX = {
    1: (0.10, 0.45, 0.25, 0.20), 2: (0.15, 0.60, 0.10, 0.15), 3: (0.15, 0.60, 0.10, 0.15), 4: (0.15, 0.60, 0.10, 0.15),
    5: (0.15, 0.60, 0.10, 0.15), 6: (0.20, 0.30, 0.10, 0.40), 7: (0.20, 0.30, 0.10, 0.40), 8: (0.50, 0.20, 0.10, 0.20),
    9: (0.50, 0.20, 0.10, 0.20), 10: (0.15, 0.15, 0.45, 0.25), 11: (0.15, 0.15, 0.45, 0.25), 12: (0.10, 0.15, 0.30, 0.45),
}
FRUIT_MIX = {True: (0.70, 0.22, 0.08), False: (0.30, 0.30, 0.40)}
SECTORS = {
    "norte": {"base": 300, "seasonal": False, "weeks": None},
    "sul": {"base": 240, "seasonal": True, "weeks": None},
    "serra": {"base": 200, "seasonal": True, "weeks": None},
    "leste": {"base": 210, "seasonal": True, "weeks": None},
    "controle": {"base": 48, "seasonal": False, "weeks": None},
    "oeste": {"base": 230, "seasonal": True, "weeks": 15},
    "vale": {"base": 140, "seasonal": True, "weeks": 8},
}
ROLES = {
    "norte": "estável: % de podres normal ao redor de 17% (curva normal sem sinal; previsão confiável)",
    "sul": "piora contínua de 20% para 60% (previsão passa de 50%; ajuste normal ruim por causa da tendência)",
    "serra": "assimétrico: quase sem podres, com surtos nas chuvas (fev. a mai.); curva normal prevê valores abaixo de 0%",
    "leste": "passeio aleatório: a previsão ingênua vence a reta (não confiável)",
    "controle": "amostras de referência sempre boas (sem variação)",
    "oeste": "fornecedor novo há 15 semanas (menos de 20 períodos)",
    "vale": "fornecedor novo há 8 semanas (sem teste retroativo possível)",
    "linha 1": "amostragem por foto antes da câmera: estável perto de 13% de podres",
    "linha 2": "amostragem por foto antes da câmera: estável perto de 18% de podres",
}
LINE_HISTORY = {"linha 1": (170, 0.13, 0.02), "linha 2": (140, 0.18, 0.025)}
SIZE_MM = {"boa": (56, 4), "baixa_qualidade": (42, 5), "podre": (50, 5)}
LINE_LABELS = ("boa", "baixa_qualidade", "podre")
REVIEW = 0.03
SORTED = {"baixa_qualidade": "baixa_qualidade", "podre": "podre", "queimada": "podre", "quebrada": "baixa_qualidade"}
UNSEEN = ("queimada", "quebrada")


def week_starts(monday, weeks):
    return [pd.Timestamp(monday) - pd.Timedelta(weeks=weeks - k) for k in range(weeks)]


def shutdown_week(starts):
    third = len(starts) // 3
    return next((k for k in range(third, len(starts)) if (starts[k] + pd.Timedelta(days=3)).month == 7), third)


def rotten_share(name, k, weeks, month, rng, walk):
    if name == "norte":
        return rng.normal(0.17, 0.025)
    if name == "sul":
        return 0.20 + 0.40 * k / max(1, weeks - 1) + rng.normal(0, 0.022)
    if name == "serra":
        return rng.beta(1.6, 11) if month in RAINY else rng.beta(0.8, 18)
    if name == "leste":
        step = walk[0] + rng.normal(0, 0.03)
        walk[0] = 0.16 - step if step < 0.08 else 1.1 - step if step > 0.55 else step
        return walk[0]
    if name == "controle":
        return 0.0
    if name == "oeste":
        return rng.normal(0.25, 0.03)
    return rng.normal(0.21, 0.03)


def painel_events(monday, weeks=156, seed=7):
    rng = np.random.default_rng(seed)
    starts = week_starts(monday, weeks)
    off = shutdown_week(starts)
    walk = [0.30]
    spec = []
    for k, start in enumerate(starts):
        month = (start + pd.Timedelta(days=3)).month
        lo = start + pd.Timedelta(days=3) if k == 0 else start
        days = (start + pd.Timedelta(days=7) - lo).days
        for name, s in SECTORS.items():
            p = float(np.clip(rotten_share(name, k, weeks, month, rng, walk), 0, 1))
            if k == off or (s["weeks"] and k < weeks - s["weeks"]):
                continue
            n = s["base"] if name == "controle" else rng.poisson(s["base"] * (VOLUME[month] if s["seasonal"] else 1) * days / 7)
            bad = rng.binomial(n, p)
            mix = FRUIT_MIX[month in HARVEST]
            for label, count in (("nao_podre", n - bad), *zip(DEFECTS, rng.multinomial(bad, DEFECT_MIX[month]))):
                for fruit, c in zip(FRUITS, rng.multinomial(count, mix)):
                    if c:
                        spec.append((lo, days, name, fruit, label, c))
    raw = pd.concat([expand(spec, rng), line_history(starts, off, seed)], ignore_index=True)
    tie(raw, starts[weeks - 6], rng)
    return FA.to_events(raw)


def line_history(starts, off, seed):
    rng = np.random.default_rng(seed + 3)
    spec = []
    for k, start in enumerate(starts):
        if k == off:
            continue
        month = (start + pd.Timedelta(days=3)).month
        lo = start + pd.Timedelta(days=3) if k == 0 else start
        days = (start + pd.Timedelta(days=7) - lo).days
        for name, (base, mean, sd) in LINE_HISTORY.items():
            n = rng.poisson(base * VOLUME[month] * days / 7)
            bad = rng.binomial(n, float(np.clip(rng.normal(mean, sd), 0, 1)))
            for label, count in (("nao_podre", n - bad), *zip(DEFECTS, rng.multinomial(bad, DEFECT_MIX[month]))):
                if count:
                    spec.append((lo, days, name, "caju", label, count))
    return expand(spec, rng)


def sorting(painel, seed=7):
    rng = np.random.default_rng(seed + 2)
    kind = painel["deformity_type"]
    unseen = kind.isin(UNSEEN).to_numpy()
    sure = rng.beta(12, 1.5, len(painel))
    unsure = rng.beta(5, 3, len(painel))
    return kind.map(SORTED).fillna("boa").to_numpy(), np.clip(np.where(unseen, unsure, sure), 0.34, 1.0)


def expand(spec, rng):
    s = pd.DataFrame(spec, columns=["start", "days", "sector", "fruit", "label", "n"])
    rep = s.loc[s.index.repeat(s["n"])].reset_index(drop=True)
    offs = np.floor(rng.random(len(rep)) * rep["days"].to_numpy() * 86400)
    ts = pd.to_datetime(rep["start"].to_numpy()) + pd.to_timedelta(offs, unit="s")
    return pd.DataFrame({"timestamp": ts, "sector": rep["sector"].to_numpy(), "fruit": rep["fruit"].to_numpy(), "label": rep["label"].to_numpy()})


def tie(raw, start, rng):
    rows = raw.index[(raw["timestamp"] >= start) & (raw["timestamp"] < start + pd.Timedelta(days=7)) & raw["label"].isin(DEFECTS)]
    counts = raw.loc[rows, "label"].value_counts()
    a, b = counts.index[:2]
    diff = int(counts[a] - counts[b])
    pool = rng.permutation(rows[raw.loc[rows, "label"].to_numpy() == a])
    if diff % 2:
        third = counts.index[2] if len(counts) > 2 else b
        raw.loc[pool[0], "label"] = third
        pool, diff = pool[1:], diff - 1
    raw.loc[pool[: diff // 2], "label"] = b


def line_plan(index, minutes, base_mix, max_rotten):
    t = np.arange(minutes)
    podre = np.full(minutes, base_mix[2])
    review = np.full(minutes, REVIEW)
    stop = np.zeros(minutes, bool)
    size = np.zeros(minutes)
    if index == 0:
        lots = np.minimum(t // 90, 5)
        podre[(t >= 180) & (t < 270)] = 0.32
        podre[(t >= 360) & (t < 450)] = max_rotten if max_rotten else base_mix[2]
        stop[(t >= 300) & (t < 318)] = True
    elif index == 1:
        edges = [0, 90, 180, 270, 282, 372]
        lots = np.searchsorted(edges, t, side="right") - 1
        podre[(t >= 270) & (t < 282)] = 0.17
        bump = np.clip(np.minimum(t - 95, 265 - t) / 15, 0, 1)
        podre += 0.025 * bump
        review[(t >= 330) & (t < 362)] = 0.35
        size[(t >= 90) & (t < 180)] = -5
    else:
        lots = t // 90
    return lots, podre, review, stop, size


def line_events(cams, start, end, seed=7):
    rng = np.random.default_rng(seed + 1)
    start = pd.Timestamp(start).ceil("5min")
    minutes = max(0, int((pd.Timestamp(end) - start) / pd.Timedelta(minutes=1)))
    out = []
    for index, cam in enumerate(cams):
        sim = cam.get("sim", {})
        rate = sim.get("rate_per_s", 1.5)
        mix = np.asarray(sim.get("mix", [0.6, 0.25, 0.15]), float)
        mix = mix / mix.sum()
        lots, podre, review, stop, size = line_plan(index, minutes, mix, cam.get("max_rotten_share"))
        rows = []
        for m in range(minutes):
            if stop[m]:
                continue
            q = podre[m]
            p = np.array([mix[0], mix[1]]) * (1 - q) / (mix[0] + mix[1])
            arrivals = np.sort(rng.uniform(0, 60, rng.poisson(rate * 60)))
            labels = rng.choice(3, size=len(arrivals), p=[p[0], p[1], q])
            flagged = rng.random(len(arrivals)) < review[m]
            for s, k, r in zip(arrivals, labels, flagged):
                label = LINE_LABELS[k]
                mean, sd = SIZE_MM[label]
                rows.append((
                    pd.Timestamp(start) + pd.Timedelta(minutes=m, seconds=float(s)), label, bool(r), f"L{index + 1}-{pd.Timestamp(start):%m%d}-{lots[m] + 1:02d}",
                    float(rng.normal(mean + size[m], sd)), float(np.clip(rng.beta(4, 4) if r else rng.beta(12, 1.5), 0.34, 1.0)),
                ))
        frame = pd.DataFrame(rows, columns=["timestamp", "label", "needs_review", "lot", "size_mm", "confidence"])
        frame["timestamp"] = frame["timestamp"].dt.round("us")
        frame["camera"] = cam["slug"]
        out.append(frame)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["timestamp", "label", "needs_review", "lot", "size_mm", "confidence", "camera"])
