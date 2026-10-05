import os
import shutil
import torch
from data_synth import make_synthetic_dataset
from train import build_loaders, build_model, train_one_epoch, evaluate
from infer import predict


def run():
    root = "data_synthetic_test"
    shutil.rmtree(root, ignore_errors=True)
    classes_expected = ["W180", "W320", "W400"]
    make_synthetic_dataset(root, classes_expected, n_per_class=24, img_size=64)

    train_loader, val_loader, classes = build_loaders(root, img_size=64, batch_size=8)
    assert classes == classes_expected, f"class mismatch: {classes}"

    device = torch.device("cpu")
    model = build_model(len(classes), pretrained=False).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = torch.nn.CrossEntropyLoss()

    losses = []
    for _ in range(3):
        loss = train_one_epoch(model, train_loader, optimizer, criterion, device)
        losses.append(loss)
    assert losses[-1] < losses[0], f"loss did not decrease: {losses}"

    val_loss, val_acc, recall = evaluate(model, val_loader, criterion, device, len(classes))
    assert 0.0 <= val_acc <= 1.0
    assert val_loss > 0.0
    assert len(recall) == len(classes)

    ckpt_path = "test_checkpoint.pt"
    torch.save({"model_state": model.state_dict(), "classes": classes}, ckpt_path)
    ckpt = torch.load(ckpt_path, map_location=device)
    reloaded = build_model(len(ckpt["classes"]), pretrained=False)
    reloaded.load_state_dict(ckpt["model_state"])
    reloaded.eval()

    sample_image = f"{root}/val/{classes[0]}/{classes[0]}_0.png"
    label, conf = predict(reloaded, ckpt["classes"], sample_image, device, img_size=64)
    assert label in classes
    assert 0.0 <= conf <= 1.0

    model.eval()
    with torch.no_grad():
        images, labels = next(iter(val_loader))
        out_a = model(images)
        out_b = reloaded(images)
        assert torch.allclose(out_a, out_b, atol=1e-5), "reload mismatch"

    shutil.rmtree(root, ignore_errors=True)
    os.remove(ckpt_path)
    print("ALL CHECKS PASSED")
    print("losses:", losses)
    print("val_loss:", val_loss, "val_acc:", val_acc)


if __name__ == "__main__":
    run()