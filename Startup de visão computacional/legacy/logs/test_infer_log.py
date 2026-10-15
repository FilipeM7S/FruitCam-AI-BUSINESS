import contextlib
import io
import os
import sys
import tempfile
import types
from unittest import mock

import pandas as pd

import analytics as A

HERE = os.path.dirname(os.path.abspath(__file__))
CLASSES = ["nao_podre", "podre"]
PREDICTION = ("podre", 0.8765432)


def stub_modules():
    torch = types.ModuleType("torch")
    torch.device = lambda name: name
    torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    torchvision = types.ModuleType("torchvision")
    torchvision.transforms = types.ModuleType("torchvision.transforms")
    train = types.ModuleType("train")
    train.build_model = lambda *args, **kwargs: None
    return {"torch": torch, "torchvision": torchvision, "torchvision.transforms": torchvision.transforms, "train": train}


def run_main(infer, *argv):
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with mock.patch.object(sys, "argv", ["infer.py", *argv]), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            infer.main()
        except SystemExit as exit_:
            code = exit_.code
    return code, out.getvalue(), err.getvalue()


def test_infer_logs_record():
    with mock.patch.dict(sys.modules, stub_modules()), mock.patch.object(sys, "path", [HERE] + sys.path):
        sys.modules.pop("infer", None)
        import infer

        infer.load_model = lambda checkpoint, device: (None, CLASSES)
        infer.predict = lambda model, classes, image, device, img_size=224: PREDICTION
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "log.csv")
            code, plain, _ = run_main(infer, "m.pt", "x.jpg")
            assert code == 0 and plain == f"{PREDICTION[0]} {PREDICTION[1]:.4f}\n", (code, plain)

            for lot in ("L1", "L2"):
                code, out, err = run_main(infer, "m.pt", "x.jpg", "--log", log, "--sector", "norte", "--fruit", "caju", "--lot", lot)
                assert code == 0 and out == plain, (code, out, err)
            df = A.load_records(log)
            assert len(df) == 2 and df["lot"].tolist() == ["L1", "L2"]
            assert (df["label"] == PREDICTION[0]).all() and (df["sector"] == "norte").all() and (df["fruit"] == "caju").all()
            assert (abs(df["confidence"] - PREDICTION[1]) < 5e-7).all()
            assert (abs((pd.Timestamp.now() - df["timestamp"]).dt.total_seconds()) < 300).all()

            no_lot = os.path.join(d, "nolot.csv")
            code, _, _ = run_main(infer, "m.pt", "x.jpg", "--log", no_lot, "--sector", "sul", "--fruit", "melao")
            assert code == 0 and A.load_records(no_lot)["lot"].isna().all()

            for missing in (["--sector", "norte"], ["--fruit", "caju"], []):
                bad_log = os.path.join(d, "never.csv")
                code, out, err = run_main(infer, "m.pt", "x.jpg", "--log", bad_log, *missing)
                assert code == 2 and "--log requires --sector and --fruit" in err, (code, err)
                assert out == "" and not os.path.exists(bad_log)

            code, out, _ = run_main(infer, "m.pt", "x.jpg", "--sector", "norte", "--fruit", "caju")
            assert code == 0 and out == plain
            assert set(os.listdir(d)) == {"log.csv", "nolot.csv"}
    assert "infer" not in sys.modules
    print("test_infer_logs_record OK")


if __name__ == "__main__":
    test_infer_logs_record()
    print("ALL INFER LOG CHECKS PASSED")