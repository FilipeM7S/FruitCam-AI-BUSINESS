import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from belt.classify import CropClassifier
from belt.stats import wilson
from training import cashew_data as D
from eval_real_belt import dhash
from training.train_v3 import subset

OUT = ROOT / "docs" / "reports" / "calibration"
K = len(D.CLASSES)
GOOD, ROTTEN = D.CLASSES.index("boa"), D.CLASSES.index("podre")
CUTS = [round(0.30 + 0.05 * i, 2) for i in range(14)]
LIMIT = 0.05
BITS = np.array([bin(i).count("1") for i in range(256)], np.uint8)


def logits_of(rows, files, classifier, batch=128):
    out = []
    for i in range(0, len(rows), batch):
        crops = [cv2.cvtColor(np.asarray(files.image(r)), cv2.COLOR_RGB2BGR) for r in rows[i:i + batch]]
        out.append(np.log(np.clip(classifier.probs(crops), 1e-12, 1)) * classifier.temperature)
    return np.concatenate(out)


def hashes(rows, files):
    return np.stack([dhash(cv2.cvtColor(np.asarray(files.image(r)), cv2.COLOR_RGB2BGR)) for r in rows])


def nearest(a, b, block=200):
    return np.concatenate([BITS[a[i:i + block, None, :] ^ b[None, :, :]].sum(axis=2).min(axis=1) for i in range(0, len(a), block)])


def leakage(test, train_rows, files, p):
    distance = nearest(hashes(test["rows"], files), hashes(train_rows, files))
    y, pred = test["y"], p.argmax(axis=1)
    out = {"what": "for every test crop, the smallest Hamming distance between its 64-bit difference hash and the hash of any training crop; a small distance means an almost identical picture", "training_crops": len(train_rows), "test_crops": int(len(y)), "limits": {}}
    for limit in (0, 4, 8):
        clean = distance > limit
        recalls = [float((pred[clean & (y == c)] == c).mean()) for c in range(K)]
        out["limits"][str(limit)] = {"test_crops_with_a_near_copy_in_training": int((~clean).sum()), "per_class": {c: int((~clean & (y == i)).sum()) for i, c in enumerate(D.CLASSES)}, "n_without_them": int(clean.sum()), "accuracy_without_them": float((pred[clean] == y[clean]).mean()), "balanced_accuracy_without_them": float(np.mean(recalls))}
    out["not_covered"] = "the same fruit photographed from another position or distance is not an almost identical picture and is not caught by this check; the photos carry no position data to test it"
    return out


def softmax(z, t=1.0):
    z = z / t
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def nll(z, y, t):
    return float(-np.log(np.clip(softmax(z, t)[np.arange(len(y)), y], 1e-12, 1)).mean())


def fit_temperature(z, y):
    return float(np.exp(minimize_scalar(lambda s: nll(z, y, np.exp(s)), bounds=(-2, 2), method="bounded").x))


def ece(p, y, bins=15):
    conf, pred = p.max(axis=1), p.argmax(axis=1)
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            total += m.mean() * abs((pred[m] == y[m]).mean() - conf[m].mean())
    return float(total)


def reliability(conf, hit, bins=10):
    edges = np.linspace(0, 1, bins + 1)
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            rows.append({"from": float(lo), "to": float(hi), "n": int(m.sum()), "mean_confidence": float(conf[m].mean()), "observed": float(hit[m].mean()), "observed_ci95": wilson(int(hit[m].sum()), int(m.sum()))})
    return rows


def groups_of(photos):
    index = {}
    for i, p in enumerate(photos):
        index.setdefault(p, []).append(i)
    return [np.array(v) for v in index.values()]


def by_photo(photos, draws, seed, measure):
    rng = np.random.default_rng(seed)
    groups = groups_of(photos)
    values = np.array([measure(np.concatenate([groups[j] for j in rng.integers(0, len(groups), len(groups))])) for _ in range(draws)])
    return np.percentile(values, [2.5, 97.5], axis=0).T.tolist() if values.ndim > 1 else [float(v) for v in np.percentile(values, [2.5, 97.5])]


def pr_curve(score, positive):
    order = np.argsort(-score)
    hits = np.cumsum(positive[order])
    precision, recall = hits / np.arange(1, len(score) + 1), hits / max(int(positive.sum()), 1)
    last = np.r_[np.flatnonzero(np.diff(score[order]) != 0), len(score) - 1]
    average = float(np.sum(np.diff(np.r_[0.0, recall[last]]) * precision[last]))
    return {"threshold": score[order][last].tolist(), "precision": precision[last].tolist(), "recall": recall[last].tolist(), "average_precision": average}


def decide(p, cut):
    pred = p.argmax(axis=1)
    if cut is None:
        return pred
    others = p.copy()
    others[:, ROTTEN] = -1
    return np.where(p[:, ROTTEN] >= cut, ROTTEN, others.argmax(axis=1))


def point(p, y, cut):
    pred = decide(p, cut)
    rotten, called = y == ROTTEN, pred == ROTTEN
    hit, good = int((rotten & called).sum()), int((rotten & (pred == GOOD)).sum())
    recalls = [float((pred[y == c] == c).mean()) for c in range(K)]
    return {
        "rule": "maior probabilidade" if cut is None else f"podre só com probabilidade de podre de pelo menos {cut:.2f}",
        "cut": cut,
        "n": int(len(y)),
        "rotten_precision": {"k": hit, "n": int(called.sum()), "value": hit / int(called.sum()) if called.any() else None, "ci95": wilson(hit, int(called.sum()))},
        "rotten_recall": {"k": hit, "n": int(rotten.sum()), "value": hit / int(rotten.sum()), "ci95": wilson(hit, int(rotten.sum()))},
        "rotten_called_good": {"k": good, "n": int(rotten.sum()), "value": good / int(rotten.sum()), "ci95": wilson(good, int(rotten.sum()))},
        "good_called_rotten": {"k": int(((y == GOOD) & called).sum()), "n": int((y == GOOD).sum())},
        "recall": dict(zip(D.CLASSES, recalls)),
        "balanced_accuracy": float(np.mean(recalls)),
        "accuracy": float((pred == y).mean()),
    }


def measure(model, data, sources, cap, seed, draws):
    started = time.perf_counter()
    rows = D.manifest(data)
    files = D.CropFiles([], None, data)
    classifier = CropClassifier(model)
    parts = {}
    for split in ("val", "test"):
        picked = subset(rows, split, sources, cap, seed)
        parts[split] = {"rows": picked, "z": logits_of(picked, files, classifier), "y": np.array([D.CLASSES.index(r["label"]) for r in picked]), "photos": [f"{r['source']}:{r['photo']}" for r in picked]}
        print(f"{split}: {len(picked)} crops from {len(set(parts[split]['photos']))} photos [{time.perf_counter() - started:.0f} s]", flush=True)
    val, test = parts["val"], parts["test"]
    shared = set(val["photos"]) & set(test["photos"])
    temperature = fit_temperature(val["z"], val["y"])
    before, after = softmax(test["z"], 1.0), softmax(test["z"], temperature)
    y, photos = test["y"], test["photos"]
    ci = by_photo(photos, draws, seed, lambda i: [ece(before[i], y[i]), ece(after[i], y[i]), ece(before[i], y[i]) - ece(after[i], y[i])])
    val_p = softmax(val["z"], temperature)
    val_points = [point(val_p, val["y"], cut) for cut in [None, *CUTS]]
    allowed = [v for v in val_points if v["cut"] is not None and v["rotten_called_good"]["value"] <= LIMIT]
    proposed = max(allowed, key=lambda v: v["cut"])["cut"] if allowed else None
    test_points = [point(after, y, cut) for cut in [None, *CUTS]]
    default, chosen = test_points[0], next((t for t in test_points if t["cut"] == proposed), None)
    holds = bool(chosen and chosen["rotten_called_good"]["value"] <= LIMIT and chosen["rotten_precision"]["value"] > default["rotten_precision"]["value"])
    seen = [t["cut"] for t in test_points if t["cut"] is not None and t["rotten_called_good"]["value"] <= LIMIT and t["rotten_precision"]["value"] > default["rotten_precision"]["value"]]
    gain = None
    if chosen:
        gain = {"rotten_precision_change_ci95": by_photo(photos, draws, seed + 1, lambda i: (point(after[i], y[i], proposed)["rotten_precision"]["value"] or 0) - (point(after[i], y[i], None)["rotten_precision"]["value"] or 0)), "rotten_called_good_ci95_by_photo": by_photo(photos, draws, seed + 2, lambda i: point(after[i], y[i], proposed)["rotten_called_good"]["value"])}
    conf_b, conf_a = before.max(axis=1), after.max(axis=1)
    leak = leakage(test, subset(rows, "train", sources), files, after)
    print(f"near-copy check done [{time.perf_counter() - started:.0f} s]", flush=True)
    return {
        "what": "calibration and operating point of the deployed classifier on field photos (fruit on the tree); nothing here was measured on a belt",
        "model": {"file": Path(model).name, "temperature_in_the_weights": classifier.temperature, "reject_below": classifier.reject_below},
        "data": {
            "dataset": "cashew_v3 crops: Ghana photos and the second Uganda label batch (field photos)",
            "split": "by source photo; no photo in two splits",
            "validation": {"crops": len(val["y"]), "photos": len(set(val["photos"])), "per_class": {c: int((val["y"] == i).sum()) for i, c in enumerate(D.CLASSES)}},
            "test": {"crops": len(y), "photos": len(set(photos)), "per_class": {c: int((y == i).sum()) for i, c in enumerate(D.CLASSES)}},
            "photos_in_both_splits": len(shared),
            "near_copies_between_training_and_test": leak,
        },
        "calibration": {
            "method": "temperature scaling: one number fitted on the validation crops by minimum negative log-likelihood; the test crops are only used to report",
            "temperature_fitted_on_validation": temperature,
            "test": {
                "n": int(len(y)),
                "ece_before": ece(before, y),
                "ece_after": ece(after, y),
                "ece_before_ci95": ci[0],
                "ece_after_ci95": ci[1],
                "ece_reduction_ci95": ci[2],
                "nll_before": nll(test["z"], y, 1.0),
                "nll_after": nll(test["z"], y, temperature),
                "mean_confidence_before": float(conf_b.mean()),
                "mean_confidence_after": float(conf_a.mean()),
                "accuracy": float((after.argmax(axis=1) == y).mean()),
            },
            "reliability_before": reliability(conf_b, before.argmax(axis=1) == y),
            "reliability_after": reliability(conf_a, after.argmax(axis=1) == y),
            "reliability_of_the_rotten_probability_after": reliability(after[:, ROTTEN], y == ROTTEN),
        },
        "precision_recall": {c: {"positives": int((y == i).sum()), "n": int(len(y)), **pr_curve(after[:, i], y == i)} for i, c in enumerate(D.CLASSES)},
        "operating_point": {
            "rule": "answer rotten only when the calibrated probability of rotten reaches the cut; otherwise answer the more probable of the other two classes",
            "limit": f"rotten fruit called good must stay at or below {LIMIT:.0%}",
            "chosen_on": "validation: the highest cut whose share of rotten fruit called good stays within the limit",
            "proposed_cut": proposed,
            "validation": val_points,
            "test": test_points,
            "test_default": default,
            "test_proposed": chosen,
            "test_change": gain,
            "holds_on_test": holds,
            "cuts_within_the_limit_on_test_read_after_the_fact": seen,
            "status": "the app keeps answering the most probable class and keeps sending every fruit to manual review" + ("; the cut chosen on validation is a proposal that needs fresh data before any use" if holds else "; the cut chosen on validation did not keep the limit on the test crops, so nothing is proposed"),
        },
        "seconds": round(time.perf_counter() - started, 1),
    }


def pct(v, d=1):
    return "n/d" if v is None else f"{100 * v:.{d}f}%".replace(".", ",")


def frac(m):
    return f"{pct(m['value'])} ({m['k']} de {m['n']}; IC 95% {pct(m['ci95'][0])} a {pct(m['ci95'][1])})"


def markdown(r):
    c, o, d = r["calibration"], r["operating_point"], r["data"]
    t = c["test"]
    num = lambda v: f"{v:.3f}".replace(".", ",")
    lines = [
        "# Calibração e ponto de operação do belt_v3",
        "",
        "Gerado por `python tools/calibration_v3.py`. Explicação em [docs/guides/model_checks.md](../../guides/model_checks.md).",
        "",
        "**Tudo aqui é medido em fotos de fruto no pé, não em esteira.** O ponto de operação é uma proposta; o app não mudou.",
        "",
        "## Dados",
        "",
        "| Conjunto | Recortes | Fotos | boa | baixa qualidade | podre |",
        "|---|---|---|---|---|---|",
        *[f"| {name} | {d[key]['crops']} | {d[key]['photos']} | {d[key]['per_class']['boa']} | {d[key]['per_class']['baixa_qualidade']} | {d[key]['per_class']['podre']} |" for name, key in (("Validação (ajuste)", "validation"), ("Teste (relato)", "test"))],
        "",
        f"Divisão por foto. Fotos presentes nos dois conjuntos: {d['photos_in_both_splits']}.",
        "",
        "### Cópias quase iguais entre treino e teste",
        "",
        f"Cada um dos {d['near_copies_between_training_and_test']['test_crops']} recortes de teste foi comparado com os {d['near_copies_between_training_and_test']['training_crops']} de treino por um hash de diferença de 64 bits. Distância pequena quer dizer imagem quase idêntica.",
        "",
        "| Distância máxima | Recortes de teste com cópia no treino | Acurácia sem eles | Acurácia balanceada sem eles | n restante |",
        "|---|---|---|---|---|",
        *[f"| {k} bits | {v['test_crops_with_a_near_copy_in_training']} | {pct(v['accuracy_without_them'])} | {pct(v['balanced_accuracy_without_them'])} | {v['n_without_them']} |" for k, v in d["near_copies_between_training_and_test"]["limits"].items()],
        "",
        "O que este teste não cobre: o mesmo fruto fotografado de outra posição não é uma imagem quase idêntica, e as fotos não trazem posição para conferir isso.",
        "",
        "## Calibração",
        "",
        f"Temperatura ajustada só na validação: **{num(c['temperature_fitted_on_validation'])}** (a gravada no modelo é {num(r['model']['temperature_in_the_weights'])}).",
        "",
        f"| No teste (n = {t['n']}) | Antes | Depois |",
        "|---|---|---|",
        f"| ECE, 15 faixas | {num(t['ece_before'])} (IC 95% {num(t['ece_before_ci95'][0])} a {num(t['ece_before_ci95'][1])}) | {num(t['ece_after'])} (IC 95% {num(t['ece_after_ci95'][0])} a {num(t['ece_after_ci95'][1])}) |",
        f"| Log-verossimilhança negativa | {num(t['nll_before'])} | {num(t['nll_after'])} |",
        f"| Confiança média | {pct(t['mean_confidence_before'])} | {pct(t['mean_confidence_after'])} |",
        f"| Acurácia | {pct(t['accuracy'])} | {pct(t['accuracy'])} |",
        "",
        f"Redução do ECE: IC 95% de {num(t['ece_reduction_ci95'][0])} a {num(t['ece_reduction_ci95'][1])} (bootstrap por foto).",
        "",
        "### Confiabilidade depois da calibração",
        "",
        "| Faixa de confiança | n | Confiança média | Acerto observado (IC 95%) |",
        "|---|---|---|---|",
        *[f"| {pct(b['from'], 0)} a {pct(b['to'], 0)} | {b['n']} | {pct(b['mean_confidence'])} | {pct(b['observed'])} ({pct(b['observed_ci95'][0])} a {pct(b['observed_ci95'][1])}) |" for b in c["reliability_after"]],
        "",
        "### A probabilidade de podre diz a verdade?",
        "",
        "| Probabilidade de podre | n | Média | Fração que era podre (IC 95%) |",
        "|---|---|---|---|",
        *[f"| {pct(b['from'], 0)} a {pct(b['to'], 0)} | {b['n']} | {pct(b['mean_confidence'])} | {pct(b['observed'])} ({pct(b['observed_ci95'][0])} a {pct(b['observed_ci95'][1])}) |" for b in c["reliability_of_the_rotten_probability_after"]],
        "",
        "## Precisão média por classe (curva precisão × sensibilidade, teste)",
        "",
        "| Classe | Positivos | n | Precisão média |",
        "|---|---|---|---|",
        *[f"| {name} | {v['positives']} | {v['n']} | {pct(v['average_precision'])} |" for name, v in r["precision_recall"].items()],
        "",
        "## Ponto de operação para \"podre\"",
        "",
        "Regra testada: responder \"podre\" só quando a probabilidade de podre passa de um corte; abaixo dele, responder a mais provável das outras duas classes.",
        f"Limite: no máximo {pct(LIMIT, 0)} das podres chamadas de boas. O corte é escolhido na validação e relatado no teste.",
        "",
        f"### No teste (n = {t['n']})",
        "",
        "| Regra | Precisão de podre | Sensibilidade de podre | Podres chamadas de boas | Boas chamadas de podres | Acurácia balanceada |",
        "|---|---|---|---|---|---|",
        *[f"| {'**' if p['cut'] == o['proposed_cut'] else ''}{'maior probabilidade (atual)' if p['cut'] is None else 'corte ' + f'{p['cut']:.2f}'.replace('.', ',')}{' (escolhido na validação)**' if p['cut'] == o['proposed_cut'] else ''} | {frac(p['rotten_precision'])} | {frac(p['rotten_recall'])} | {frac(p['rotten_called_good'])} | {p['good_called_rotten']['k']} de {p['good_called_rotten']['n']} | {pct(p['balanced_accuracy'])} |" for p in o["test"]],
        "",
        "### Na validação (onde o corte foi escolhido)",
        "",
        "| Regra | Precisão de podre | Sensibilidade de podre | Podres chamadas de boas |",
        "|---|---|---|---|",
        *[f"| {'maior probabilidade' if p['cut'] is None else 'corte ' + f'{p['cut']:.2f}'.replace('.', ',')} | {frac(p['rotten_precision'])} | {frac(p['rotten_recall'])} | {frac(p['rotten_called_good'])} |" for p in o["validation"]],
        "",
    ]
    if o["test_proposed"]:
        a, b, g = o["test_default"], o["test_proposed"], o["test_change"]
        lines += [
            "## Leitura",
            "",
            f"- Com o corte escolhido na validação ({f'{o['proposed_cut']:.2f}'.replace('.', ',')}), a precisão de podre no teste vai de {pct(a['rotten_precision']['value'])} para {pct(b['rotten_precision']['value'])}. Diferença: IC 95% de {pct(g['rotten_precision_change_ci95'][0])} a {pct(g['rotten_precision_change_ci95'][1])} (bootstrap por foto).",
            f"- O preço: a sensibilidade de podre cai de {pct(a['rotten_recall']['value'])} para {pct(b['rotten_recall']['value'])}, e as podres chamadas de boas vão de {pct(a['rotten_called_good']['value'])} para {pct(b['rotten_called_good']['value'])} (IC 95% por foto: {pct(g['rotten_called_good_ci95_by_photo'][0])} a {pct(g['rotten_called_good_ci95_by_photo'][1])}).",
            f"- **{'O limite se manteve no teste' if o['holds_on_test'] else 'Resultado negativo: o limite de ' + pct(LIMIT, 0) + ' não se manteve no teste'}.** {'Ainda assim é só uma proposta' if o['holds_on_test'] else 'O corte escolhido na validação não é proposto, e fica a regra atual'}.",
            f"- Mesmo a regra atual não permite afirmar o limite: {a['rotten_called_good']['k']} de {a['rotten_called_good']['n']} podres chamadas de boas dá IC 95% de {pct(a['rotten_called_good']['ci95'][0])} a {pct(a['rotten_called_good']['ci95'][1])}. Com {a['rotten_called_good']['n']} frutas podres no teste, nenhuma regra pode ser certificada abaixo de {pct(LIMIT, 0)}.",
            f"- Lidos depois de ver o teste, e por isso só indicativos: os cortes {', '.join(f'{c:.2f}'.replace('.', ',') for c in o['cuts_within_the_limit_on_test_read_after_the_fact']) or 'nenhum'} ficam dentro do limite na estimativa pontual e têm precisão maior que a atual. Escolher um deles agora seria escolher olhando o teste.",
            "- Nada disso foi medido em esteira. O app continua respondendo a classe mais provável e mandando toda fruta para conferência.",
            "",
        ]
    else:
        lines += ["## Leitura", "", f"Nenhum corte manteve as podres chamadas de boas em até {pct(LIMIT, 0)} na validação. Fica a regra atual.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=str(ROOT / "models" / "belt_v3.pt"))
    parser.add_argument("--data", default=str(D.OUT))
    parser.add_argument("--eval-cap", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()
    report = json.loads(Path(args.model).with_name(Path(args.model).stem + "_eval.json").read_text(encoding="utf-8"))
    result = measure(args.model, args.data, report["data"]["sources_used"], args.eval_cap, args.seed, args.bootstrap)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "calibration.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out / "report.md").write_text(markdown(result), encoding="utf-8")
    t, o = result["calibration"]["test"], result["operating_point"]
    print(f"temperature fitted on validation {result['calibration']['temperature_fitted_on_validation']:.3f}; test ECE {t['ece_before']:.4f} -> {t['ece_after']:.4f}; proposed cut {o['proposed_cut']}; {result['seconds']} s")


if __name__ == "__main__":
    main()
