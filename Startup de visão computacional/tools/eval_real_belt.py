import argparse
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import capture_tray
from belt.classify import CropClassifier
from belt.dataset import order, read_manifest
from belt.stats import wilson

CLASSES = ["boa", "baixa_qualidade", "podre"]
GOOD, ROTTEN = 0, 2
CUTS = [round(0.35 + 0.05 * i, 2) for i in range(13)] + [0.99]


def load(sessions):
    rows, metas = [], []
    for root in map(Path, sessions):
        meta = capture_tray.session_of(root)
        if meta is None:
            raise SystemExit(f"{root}: não é uma sessão gravada por tools/capture_tray.py (falta session.json)")
        metas.append(meta)
        for r in read_manifest(root):
            if r["label"] in CLASSES:
                rows.append({**r, "root": root, "session": meta["session"], "tray": f"{meta['session']}/{r['batch']}", "fruit_id": f"{meta['session']}/{r['fruit']}"})
    return rows, metas


def dhash(image):
    small = cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (9, 8), interpolation=cv2.INTER_AREA)
    return np.packbits((small[:, 1:] > small[:, :-1]).ravel())


def fruits_of(rows, classifier, batch=128):
    groups = {}
    for r in rows:
        groups.setdefault(r["fruit_id"], []).append(r)
    crops = [cv2.imread(str(r["root"] / r["file"])) for r in rows]
    missing = [r["file"] for r, c in zip(rows, crops) if c is None]
    if missing:
        raise SystemExit(f"{len(missing)} recortes do manifesto não puderam ser lidos, por exemplo {missing[0]}")
    probs = np.concatenate([classifier.probs(crops[i:i + batch]) for i in range(0, len(crops), batch)]) if crops else np.zeros((0, len(CLASSES)), np.float32)
    at = {id(r): i for i, r in enumerate(rows)}
    fruits = []
    for fruit_id, views in groups.items():
        index = [at[id(v)] for v in views]
        first = min(index)
        fruits.append({"fruit": fruit_id, "tray": views[0]["tray"], "session": views[0]["session"], "y": CLASSES.index(views[0]["label"]), "p": probs[index].mean(axis=0), "views": len(views), "sha": hashlib.sha256((rows[first]["root"] / rows[first]["file"]).read_bytes()).hexdigest(), "hash": dhash(crops[first])})
    return fruits


def scores(y, pred):
    k = len(CLASSES)
    confusion = [[int(((y == i) & (pred == j)).sum()) for j in range(k)] for i in range(k)]
    per_class = {}
    for c, name in enumerate(CLASSES):
        support, called, hit = sum(confusion[c]), sum(confusion[i][c] for i in range(k)), confusion[c][c]
        per_class[name] = {"n": support, "recall": hit / support if support else None, "recall_ci95": wilson(hit, support), "called": called, "precision": hit / called if called else None, "precision_ci95": wilson(hit, called)}
    present = [per_class[c]["recall"] for c in CLASSES if per_class[c]["n"]]
    rotten = sum(confusion[ROTTEN])
    return {
        "n": int(len(y)),
        "accuracy": float((y == pred).mean()) if len(y) else None,
        "accuracy_ci95_wilson": wilson(int((y == pred).sum()), len(y)),
        "balanced_accuracy": float(np.mean(present)) if present else None,
        "classes_present": [c for c in CLASSES if per_class[c]["n"]],
        "confusion_rows_true_cols_called": confusion,
        "per_class": per_class,
        "rotten_called_good": {"k": confusion[ROTTEN][GOOD], "n": rotten, "rate": confusion[ROTTEN][GOOD] / rotten if rotten else None, "ci95": wilson(confusion[ROTTEN][GOOD], rotten)},
    }


def bootstrap(y, pred, trays, draws, seed):
    rng = np.random.default_rng(seed)
    by_class = {c: sorted({t for t, label in zip(trays, y) if label == c}) for c in sorted(set(y.tolist()))}
    index = {t: np.flatnonzero(np.array(trays) == t) for t in set(trays)}
    by_tray = all(len(names) >= 2 for names in by_class.values())
    acc, bal = [], []
    for _ in range(draws):
        if by_tray:
            picked = np.concatenate([index[names[j]] for names in by_class.values() for j in rng.integers(0, len(names), len(names))])
        else:
            picked = np.concatenate([rng.choice(rows, len(rows)) for rows in index.values()])
        hit = y[picked] == pred[picked]
        acc.append(hit.mean())
        bal.append(np.mean([hit[y[picked] == c].mean() for c in by_class]))
    return {
        "unit": "bandeja" if by_tray else "fruta",
        "note": "reamostra bandejas inteiras dentro de cada classe" if by_tray else "alguma classe tem uma bandeja só: reamostra frutas dentro de cada bandeja, o que ignora a diferença entre bandejas e deixa o intervalo estreito demais",
        "trays_per_class": {CLASSES[c]: len(names) for c, names in by_class.items()},
        "draws": draws,
        "accuracy_ci95": [float(np.percentile(acc, 2.5)), float(np.percentile(acc, 97.5))],
        "balanced_accuracy_ci95": [float(np.percentile(bal, 2.5)), float(np.percentile(bal, 97.5))],
    }


def at_cut(y, pred, conf, cut):
    keep = conf >= cut
    rotten = keep & (y == ROTTEN)
    hits = int((y[keep] == pred[keep]).sum())
    return {"cut": cut, "n_decided": int(keep.sum()), "n": int(len(y)), "coverage": float(keep.mean()) if len(y) else None, "accuracy_on_decided": hits / int(keep.sum()) if keep.any() else None, "accuracy_ci95": wilson(hits, int(keep.sum())), "rotten_called_good": {"k": int((pred[rotten] == GOOD).sum()), "n": int(rotten.sum())}}


def halves(fruits, seed):
    side = {}
    for c in range(len(CLASSES)):
        names = sorted({f["tray"] for f in fruits if f["y"] == c}, key=lambda t: order(t, seed))
        if len(names) < 2:
            return None
        for i, name in enumerate(names):
            side[name] = "fit" if i % 2 == 0 else "report"
    return side


def held_out_cut(fruits, y, pred, conf, target, seed):
    side = halves(fruits, seed)
    if side is None:
        return {"available": False, "why": "é preciso ter pelo menos duas bandejas de cada classe para escolher o corte numas e medir noutras"}
    part = np.array([side[f["tray"]] for f in fruits])
    fit, rep = part == "fit", part == "report"
    chosen = None
    for cut in np.round(np.arange(0.34, 0.995, 0.01), 2):
        keep = fit & (conf >= cut)
        if keep.sum() >= 30 and (y[keep] == pred[keep]).mean() >= target:
            chosen = float(cut)
            break
    near = int(sum((np.unpackbits(np.bitwise_xor(np.stack([f["hash"] for f, r in zip(fruits, rep) if r]), a["hash"]), axis=1).sum(axis=1) <= 4).sum() for a, s in zip(fruits, fit) if s)) if fit.any() and rep.any() else 0
    out = {"available": True, "target_accuracy": target, "trays": {name: where for name, where in sorted(side.items())}, "fruits": {"fit": int(fit.sum()), "report": int(rep.sum())}, "near_duplicate_pairs_between_the_two_halves": near, "cut_chosen_on_fit_trays": chosen}
    if chosen is None:
        out["why"] = f"nenhum corte chega a {target:.0%} de acerto com 30 frutas ou mais nas bandejas de ajuste"
    else:
        out["on_fit_trays"] = at_cut(y[fit], pred[fit], conf[fit], chosen)
        out["on_report_trays"] = at_cut(y[rep], pred[rep], conf[rep], chosen)
    return out


def evaluate(sessions, model, draws=2000, target=0.95, seed=0, skip_verify=False):
    damaged = {}
    if not skip_verify:
        for root in sessions:
            wrong, _ = capture_tray.verify(root)
            if wrong:
                damaged[str(root)] = wrong[:5]
    if damaged:
        raise SystemExit(f"somas de verificação não conferem, avaliação recusada: {json.dumps(damaged, ensure_ascii=False)}")
    rows, metas = load(sessions)
    if not rows:
        raise SystemExit("nenhum recorte rotulado nas sessões indicadas")
    classifier = CropClassifier(model)
    if classifier.classes != CLASSES:
        raise SystemExit(f"{model} tem as classes {classifier.classes}; esperado {CLASSES}")
    fruits = fruits_of(rows, classifier)
    y = np.array([f["y"] for f in fruits])
    probs = np.stack([f["p"] for f in fruits])
    pred, conf = probs.argmax(axis=1), probs.max(axis=1)
    trays = [f["tray"] for f in fruits]
    seen = {}
    for f in fruits:
        seen.setdefault(f["sha"], set()).add(f["tray"])
    test = any(m["purpose"] == "pipeline_test" for m in metas)
    return {
        "warning": "TESTE DE PIPELINE: os rótulos são de mentira; nenhum número aqui é desempenho" if test else None,
        "purpose": "pipeline_test" if test else "real",
        "model": {"file": Path(model).name, "sha256": capture_tray.sha256(model), "version": classifier.version, "temperature": classifier.temperature, "reject_below": classifier.reject_below},
        "data": {
            "sessions": [{k: m[k] for k in ("session", "product", "sector", "purpose")} for m in metas],
            "unit": "fruta (média das probabilidades das vistas de cada fruta)",
            "n_sessions": len(metas),
            "n_trays": len(set(trays)),
            "n_fruits": len(fruits),
            "fruits_counted_at_capture": sum(json.loads((Path(root) / e["path"]).read_text(encoding="utf-8"))["fruits"] for root, m in zip(sessions, metas) for e in m["runs"]),
            "n_crops": len(rows),
            "per_class": {c: {"trays": len({f["tray"] for f in fruits if f["y"] == i}), "fruits": int((y == i).sum()), "crops": sum(r["label"] == c for r in rows)} for i, c in enumerate(CLASSES)},
            "identical_crops_in_two_trays": sum(len(t) > 1 for t in seen.values()),
            "checksums_verified": not skip_verify,
        },
        "results": scores(y, pred),
        "bootstrap": bootstrap(y, pred, trays, draws, seed),
        "coverage_vs_accuracy": {"note": "todas as frutas; escolher o corte olhando esta tabela é otimista, o corte honesto está em held_out_cut", "rows": [at_cut(y, pred, conf, cut) for cut in CUTS]},
        "held_out_cut": held_out_cut(fruits, y, pred, conf, target, seed),
        "per_tray": {t: {"label": CLASSES[int(y[np.array(trays) == t][0])], "fruits": int((np.array(trays) == t).sum()), "accuracy": float((y == pred)[np.array(trays) == t].mean())} for t in sorted(set(trays))},
        "not_verified": "esta medição vale para estas bandejas, esta câmera e esta luz; não diz nada sobre outra linha",
    }


def pct(v):
    return "n/d" if v is None else f"{100 * v:.1f}%"


def show(report):
    d, r, b = report["data"], report["results"], report["bootstrap"]
    lines = []
    if report["warning"]:
        lines.append(report["warning"])
    lines.append(f"modelo {report['model']['file']} · {d['n_sessions']} sessão(ões), {d['n_trays']} bandejas, {d['n_fruits']} frutas com recorte (de {d['fruits_counted_at_capture']} contadas na gravação), {d['n_crops']} recortes")
    lines.append("por classe: " + "; ".join(f"{c}: {v['trays']} bandejas, {v['fruits']} frutas" for c, v in d["per_class"].items()))
    lines.append(f"acurácia {pct(r['accuracy'])} (n = {r['n']}; IC 95% {pct(b['accuracy_ci95'][0])} a {pct(b['accuracy_ci95'][1])}, bootstrap por {b['unit']})")
    lines.append(f"acurácia balanceada {pct(r['balanced_accuracy'])} (classes presentes: {len(r['classes_present'])}; IC 95% {pct(b['balanced_accuracy_ci95'][0])} a {pct(b['balanced_accuracy_ci95'][1])}; {b['note']})")
    for c, v in r["per_class"].items():
        lines.append(f"  {c:16s} sensibilidade {pct(v['recall'])} (n = {v['n']}; IC 95% {pct(v['recall_ci95'][0])} a {pct(v['recall_ci95'][1])})   precisão {pct(v['precision'])} (n = {v['called']}; IC 95% {pct(v['precision_ci95'][0])} a {pct(v['precision_ci95'][1])})")
    lines.append("matriz de confusão (linhas: verdadeiro; colunas: resposta) " + " | ".join(f"{c}: {row}" for c, row in zip(CLASSES, r["confusion_rows_true_cols_called"])))
    g = r["rotten_called_good"]
    lines.append(f"podres chamadas de boas: {g['k']} de {g['n']} ({pct(g['rate'])}; IC 95% {pct(g['ci95'][0])} a {pct(g['ci95'][1])})")
    lines.append("corte de confiança  frutas decididas  cobertura  acerto nas decididas  podres chamadas de boas")
    for row in report["coverage_vs_accuracy"]["rows"]:
        lines.append(f"  {row['cut']:.2f}              {row['n_decided']:5d} de {row['n']:<5d}   {pct(row['coverage']):>7s}    {pct(row['accuracy_on_decided']):>7s}               {row['rotten_called_good']['k']} de {row['rotten_called_good']['n']}")
    h = report["held_out_cut"]
    if not h["available"] or h["cut_chosen_on_fit_trays"] is None:
        lines.append(f"corte medido em bandejas separadas: não disponível ({h['why']})")
    else:
        a = h["on_report_trays"]
        lines.append(f"corte {h['cut_chosen_on_fit_trays']:.2f} escolhido em {h['fruits']['fit']} frutas e medido em outras {h['fruits']['report']} frutas de bandejas diferentes: decide {a['n_decided']} de {a['n']} ({pct(a['coverage'])}), acerto {pct(a['accuracy_on_decided'])} (IC 95% {pct(a['accuracy_ci95'][0])} a {pct(a['accuracy_ci95'][1])}), podres chamadas de boas {a['rotten_called_good']['k']} de {a['rotten_called_good']['n']}; pares quase iguais entre as duas metades: {h['near_duplicate_pairs_between_the_two_halves']}")
    lines.append(f"recortes idênticos em duas bandejas: {d['identical_crops_in_two_trays']}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mede um modelo nas bandejas gravadas por tools/capture_tray.py. A unidade é a fruta; as divisões são por bandeja.")
    parser.add_argument("sessions", nargs="+", help="pasta(s) de sessão")
    parser.add_argument("--model", default=str(ROOT / "models" / "belt_v3.pt"))
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--target-accuracy", type=float, default=0.95)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--skip-verify", action="store_true")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    report = evaluate(args.sessions, args.model, args.bootstrap, args.target_accuracy, args.seed, args.skip_verify)
    out = Path(args.out) if args.out else Path(args.sessions[0]) / "eval" / f"{Path(args.model).stem}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(show(report))
    print(f"relatório completo: {out}")
    return report


if __name__ == "__main__":
    main()
