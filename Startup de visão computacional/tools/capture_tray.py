import argparse
import hashlib
import json
import os
import platform
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from belt.capture import is_live
from belt.dataset import BATCH, TrayRecorder, read_manifest
from belt.pipeline import BeltPipeline

LABELS = ("boa", "baixa_qualidade", "podre")
OUT = Path(os.environ.get("FRUITCAM_DATA_STORE") or Path.home() / "FruitCamData") / "belt_sessions"
BACKENDS = {"auto": cv2.CAP_ANY, "dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF, "ffmpeg": cv2.CAP_FFMPEG}
DRIVER = {
    "exposure": cv2.CAP_PROP_EXPOSURE,
    "gain": cv2.CAP_PROP_GAIN,
    "white_balance": cv2.CAP_PROP_WB_TEMPERATURE,
    "auto_exposure": cv2.CAP_PROP_AUTO_EXPOSURE,
    "auto_white_balance": cv2.CAP_PROP_AUTO_WB,
    "width": cv2.CAP_PROP_FRAME_WIDTH,
    "height": cv2.CAP_PROP_FRAME_HEIGHT,
    "fps": cv2.CAP_PROP_FPS,
}
MANUAL = ("exposure", "gain", "white_balance")
ROTATIONS = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}
PURPOSES = {False: "real", True: "pipeline_test"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def redact(source):
    return re.sub(r"//[^/@]*@", "//***@", str(source))


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def listed(root, relative):
    path = Path(root) / relative
    return {"path": Path(relative).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}


def session_of(root):
    path = Path(root) / "session.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def problems(args):
    found = []
    for name, value in (("session", args.session), ("tray", args.tray)):
        if not value:
            found.append(f"falta --{name}")
        elif not BATCH.match(value):
            found.append(f"--{name}: use só letras, números, '.', '_' e '-' (recebido {value!r})")
    if args.label not in LABELS:
        found.append(f"falta --label: a bandeja inteira tem um rótulo só, entre {', '.join(LABELS)}")
    if not args.source:
        found.append("falta --source: número da câmera USB, endereço rtsp://, ou um arquivo de vídeo")
    if not args.px_per_mm or args.px_per_mm <= 0:
        found.append("falta --px-per-mm: ponha uma régua na esteira e divida os pixels pelos milímetros")
    if args.source and is_live(args.source):
        for name in MANUAL:
            if getattr(args, name) is None:
                found.append(f"falta --{name.replace('_', '-')}: com câmera ao vivo, fixe o valor à mão na câmera e escreva-o aqui")
    if args.source and not is_live(args.source) and not Path(args.source).exists():
        found.append(f"arquivo de vídeo não encontrado: {args.source}")
    before = session_of(Path(args.out) / args.session) if args.session and BATCH.match(args.session) else None
    if before:
        for name, value in (("product", args.product), ("sector", args.sector), ("purpose", PURPOSES[args.pipeline_test])):
            if before[name] != value:
                found.append(f"a sessão {args.session} já existe com {name} = {before[name]!r}; recebido {value!r}. Uma sessão tem um produto, um setor e uma finalidade")
    return found


def driver_state(capture):
    return {name: capture.get(prop) for name, prop in DRIVER.items()}


def apply_settings(capture, args, backend):
    capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25 if backend == "dshow" else 1)
    capture.set(cv2.CAP_PROP_AUTO_WB, 0)
    for name in MANUAL:
        capture.set(DRIVER[name], float(getattr(args, name)))


def views(capture, live, fps, rotate, roi):
    began, index = time.monotonic(), 0
    while True:
        ok, raw = capture.read()
        if not ok or raw is None:
            return
        view = cv2.rotate(raw, ROTATIONS[rotate]) if rotate else raw
        if roi:
            h, w = view.shape[:2]
            view = view[int(roi[1] * h):int(roi[3] * h), int(roi[0] * w):int(roi[2] * w)]
        yield (time.monotonic() - began if live else index / fps), raw, view
        index += 1


def record(args):
    root = Path(args.out) / args.session
    live = is_live(args.source)
    spec = int(args.source) if str(args.source).isdigit() else args.source
    capture = cv2.VideoCapture(spec, BACKENDS[args.backend])
    if not capture.isOpened():
        raise SystemExit(f"não foi possível abrir {redact(args.source)!r} com o backend {args.backend}")
    backend = capture.getBackendName()
    before = driver_state(capture)
    if live and args.apply_settings:
        apply_settings(capture, args, args.backend)
    after = driver_state(capture)
    fps = after["fps"] if after["fps"] and after["fps"] > 1 else 25.0
    if not live and args.start:
        capture.set(cv2.CAP_PROP_POS_MSEC, 1000 * args.start)
    recorder = TrayRecorder(root, args.tray, args.label, args.camera, redact(args.source), args.px_per_mm, args.frames_every)
    stream = views(capture, live, fps, args.rotate, args.roi)
    first = next(stream, None)
    if first is None:
        capture.release()
        raise SystemExit(f"nenhum quadro lido de {redact(args.source)!r}")
    t, raw, view = first
    stamp = f"COLETA · {args.session} · bandeja {args.tray} · {args.label}" + (" · TESTE DE PIPELINE" if args.pipeline_test else "")
    pipe = BeltPipeline(recorder, args.px_per_mm, view.shape[1], args.count_line, args.direction, tuple(args.belt_rows) if args.belt_rows else None, camera=args.camera, stamp=stamp)
    writer, video = None, None
    if live and not args.no_video:
        video = root / args.tray / "video" / f"{args.camera}-{args.tray}-{recorder.run}.avi"
        video.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), fps, (raw.shape[1], raw.shape[0]))
    started, first_t, frames = now(), t, 0
    try:
        while True:
            recorder.frame(t, view)
            _, drawn = pipe.process(t, view, draw=args.preview)
            frames += 1
            if writer is not None:
                writer.write(raw)
            if args.preview:
                cv2.imshow("FruitCam coleta (q para parar)", drawn)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            if args.seconds is not None and t - first_t >= args.seconds:
                break
            following = next(stream, None)
            if following is None:
                break
            t, raw, view = following
    except KeyboardInterrupt:
        pass
    capture.release()
    if writer is not None:
        writer.release()
    if args.preview:
        cv2.destroyAllWindows()
    made = [r["file"] for r in read_manifest(root) if r["batch"] == args.tray and r["run"] == recorder.run]
    made += sorted(p.relative_to(root).as_posix() for p in recorder.frames_dir.glob(f"{args.camera}-{args.tray}-{recorder.run}-*.jpg"))
    if video is not None:
        made.append(video.relative_to(root).as_posix())
    declared = {name: getattr(args, name) for name in MANUAL}
    run = {
        "session": args.session,
        "tray": args.tray,
        "label": args.label,
        "product": args.product,
        "sector": args.sector,
        "purpose": PURPOSES[args.pipeline_test],
        "operator": args.operator,
        "notes": args.notes,
        "run": recorder.run,
        "camera": args.camera,
        "source": redact(args.source),
        "source_file": None if live else {"name": Path(args.source).name, "bytes": Path(args.source).stat().st_size, "sha256": sha256(args.source), "start_s": args.start},
        "started_at": started,
        "ended_at": now(),
        "stream_seconds": round(t - first_t, 2),
        "frames": frames,
        "fruits": recorder.fruits,
        "crops": recorder.crops,
        "full_frames": recorder.frames,
        "geometry": {"px_per_mm": args.px_per_mm, "count_line": args.count_line, "direction": args.direction, "belt_rows": args.belt_rows, "roi": args.roi, "rotate": args.rotate, "frame": [int(raw.shape[1]), int(raw.shape[0])], "view": [int(view.shape[1]), int(view.shape[0])]},
        "settings": {
            "declared_by_operator": declared,
            "applied_by_tool": bool(live and args.apply_settings),
            "driver_before": before,
            "driver_after": after,
            "driver_agrees": {name: declared[name] is not None and abs(after[name] - float(declared[name])) < 1e-6 for name in MANUAL} if live else None,
        },
        "software": {"python": platform.python_version(), "opencv": cv2.__version__, "backend": backend, "tool_sha256": sha256(__file__)},
        "files": [listed(root, name) for name in made],
    }
    card = root / args.tray / "runs" / f"{recorder.run}.json"
    card.parent.mkdir(parents=True, exist_ok=True)
    card.write_text(json.dumps(run, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    session = session_of(root) or {"session": args.session, "product": args.product, "sector": args.sector, "purpose": PURPOSES[args.pipeline_test], "created_at": started, "runs": []}
    session["runs"].append({"tray": args.tray, "label": args.label, "run": recorder.run, **listed(root, card.relative_to(root))})
    manifest = root / "manifest.csv"
    session["manifest"] = listed(root, "manifest.csv") if manifest.exists() else None
    (root / "session.json").write_text(json.dumps(session, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return run


def verify(root):
    root = Path(root)
    session = session_of(root)
    if session is None:
        return [f"{root}: não há session.json"], 0
    wrong, checked = [], 0
    known = set()
    for entry in [*session["runs"], *([session["manifest"]] if session.get("manifest") else [])]:
        files = [entry]
        card = root / entry["path"]
        if card.suffix == ".json" and card.exists() and sha256(card) == entry["sha256"]:
            files += json.loads(card.read_text(encoding="utf-8"))["files"]
        for item in files:
            path = root / item["path"]
            known.add(item["path"])
            checked += 1
            if not path.exists():
                wrong.append(f"faltando: {item['path']}")
            elif path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
                wrong.append(f"alterado: {item['path']}")
    for row in read_manifest(root):
        if row["file"] not in known:
            wrong.append(f"no manifest.csv mas em nenhuma gravação: {row['file']}")
    return wrong, checked


def summary(root):
    per = {}
    for entry in (session_of(root) or {"runs": []})["runs"]:
        per.setdefault(entry["label"], set()).add(entry["tray"])
    return per


def parser():
    p = argparse.ArgumentParser(description="Grava uma bandeja separada à mão passando na esteira. Uma execução por bandeja.")
    p.add_argument("--verify", metavar="PASTA_DA_SESSAO", help="só confere as somas de verificação de uma sessão já gravada")
    p.add_argument("--session", help="identificador da sessão, por exemplo 2026-10-20-fabrica-a")
    p.add_argument("--tray", help="um nome por bandeja física, por exemplo podre-A")
    p.add_argument("--label", help="rótulo da bandeja inteira: boa, baixa_qualidade ou podre")
    p.add_argument("--source", help="número da câmera USB, rtsp://..., ou arquivo de vídeo")
    p.add_argument("--px-per-mm", type=float)
    p.add_argument("--product", default="caju")
    p.add_argument("--sector", default="")
    p.add_argument("--operator", default="")
    p.add_argument("--notes", default="")
    p.add_argument("--camera", default="campo-1")
    p.add_argument("--exposure", type=float)
    p.add_argument("--gain", type=float)
    p.add_argument("--white-balance", type=float)
    p.add_argument("--apply-settings", action="store_true", help="tenta gravar exposição, ganho e balanço de branco na câmera pelo driver")
    p.add_argument("--backend", choices=sorted(BACKENDS), default="auto")
    p.add_argument("--count-line", type=float, default=0.62)
    p.add_argument("--direction", type=int, choices=(1, -1), default=1)
    p.add_argument("--belt-rows", type=int, nargs=2)
    p.add_argument("--roi", type=float, nargs=4, metavar=("X0", "Y0", "X1", "Y1"), help="parte do quadro a usar, em frações de 0 a 1")
    p.add_argument("--rotate", type=int, choices=(0, 90, 180, 270), default=0)
    p.add_argument("--start", type=float, default=0.0, help="só para arquivo de vídeo: segundo inicial")
    p.add_argument("--seconds", type=float)
    p.add_argument("--frames-every", type=float, default=2.0)
    p.add_argument("--no-video", action="store_true", help="câmera ao vivo: não gravar o vídeo bruto")
    p.add_argument("--preview", action="store_true")
    p.add_argument("--pipeline-test", action="store_true", help="marca a sessão como teste do programa: os rótulos não valem e nenhum número é desempenho")
    p.add_argument("--out", default=str(OUT))
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if args.verify:
        wrong, checked = verify(args.verify)
        print(f"{checked} arquivos conferidos em {args.verify}: {'todos íntegros' if not wrong else str(len(wrong)) + ' com problema'}")
        for line in wrong:
            print(" ", line)
        raise SystemExit(1 if wrong else 0)
    found = problems(args)
    if found:
        raise SystemExit("gravação recusada:\n" + "\n".join(f"  - {line}" for line in found))
    try:
        run = record(args)
    except ValueError as e:
        raise SystemExit(f"gravação recusada:\n  - {e}")
    root = Path(args.out) / args.session
    print(f"sessão {run['session']} · bandeja {run['tray']} ({run['label']}): {run['fruits']} frutas, {run['crops']} recortes, {run['full_frames']} quadros inteiros, {run['frames']} quadros lidos em {run['stream_seconds']} s; {len(run['files'])} arquivos com soma de verificação em {root}")
    if run["purpose"] == "pipeline_test":
        print("TESTE DE PIPELINE: os rótulos desta sessão não valem e nenhum número dela é desempenho")
    if not run["fruits"]:
        print("nenhuma fruta cruzou a linha: confira --px-per-mm, --belt-rows, --roi, --direction e --count-line")
    if run["settings"]["driver_agrees"] and not all(run["settings"]["driver_agrees"].values()):
        print(f"atenção: o driver não confirma os valores declarados ({run['settings']['driver_agrees']}); vale o que foi fixado na câmera e anotado")
    print("bandejas gravadas até agora: " + ", ".join(f"{label} {len(trays)}" for label, trays in sorted(summary(root).items())))
    return run


if __name__ == "__main__":
    main()
