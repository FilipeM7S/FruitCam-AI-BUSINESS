import argparse
import hashlib
import json
import sys
from pathlib import Path

import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from train import build_model
from train_belt import transforms_for


class Folder(Dataset):
    def __init__(self, files, tf):
        self.files = files
        self.tf = tf

    def __len__(self):
        return len(self.files)

    def __getitem__(self, i):
        item = self.files[i]
        return self.tf(item if isinstance(item, Image.Image) else Image.open(item).convert("RGB")), 0


def crops_in(folder):
    return sorted(p for p in Path(folder).rglob("*.jpg") if "frames" not in p.parts)


@torch.no_grad()
def adapt(model, files, size, batch_size=64):
    norms = [m for m in model.modules() if isinstance(m, torch.nn.BatchNorm2d)]
    for m in norms:
        m.reset_running_stats()
        m.momentum = None
    model.train()
    _, plain = transforms_for(size)
    for x, _ in DataLoader(Folder(files, plain), batch_size=batch_size, shuffle=True, generator=torch.Generator().manual_seed(0)):
        model(x)
    model.eval()
    return len(norms)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", default=str(ROOT / "models" / "belt_v2.pt"))
    parser.add_argument("--crops", default=str(ROOT / "belt_data"), help="folder with unlabelled belt crops (labels are ignored)")
    parser.add_argument("--out")
    parser.add_argument("--min-crops", type=int, default=200)
    args = parser.parse_args()
    files = crops_in(args.crops)
    if len(files) < args.min_crops:
        raise SystemExit(f"only {len(files)} crops in {args.crops}; record at least {args.min_crops} (python manage.py record_tray <camera> --label sem_rotulo --batch <name>)")
    ck = torch.load(args.init, map_location="cpu")
    model = build_model(len(ck["classes"]), pretrained=False)
    model.load_state_dict(ck["model_state"])
    layers = adapt(model, files, int(ck["img_size"]))
    out = Path(args.out or Path(args.init).with_name(Path(args.init).stem + "_adabn.pt"))
    torch.save({**ck, "model_state": model.state_dict(), "version": out.stem, "adapted_from": Path(args.init).name, "adaptation": {"method": "AdaBN: batch-norm statistics recomputed on unlabelled belt crops", "crops": len(files), "folder": str(args.crops), "batchnorm_layers": layers, "note": "temperature and review threshold are those of the source model; refit them on labelled belt trays when available"}}, out)
    print(json.dumps({"out": str(out), "sha256": hashlib.sha256(out.read_bytes()).hexdigest(), "crops": len(files), "batchnorm_layers": layers}, indent=1))


if __name__ == "__main__":
    main()
