import argparse
from datetime import datetime

import torch
from torchvision import transforms
from PIL import Image
from train import build_model
from records import append_record


def load_model(checkpoint_path, device):
    ckpt = torch.load(checkpoint_path, map_location=device)
    model = build_model(len(ckpt["classes"]), pretrained=False)
    model.load_state_dict(ckpt["model_state"])
    model.to(device)
    model.eval()
    return model, ckpt["classes"]


def predict(model, classes, image_path, device, img_size=224):
    tf = transforms.Compose([
        transforms.Resize((img_size, img_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    image = Image.open(image_path).convert("RGB")
    tensor = tf(image).unsqueeze(0).to(device)
    with torch.no_grad():
        logits = model(tensor)
        probs = torch.softmax(logits, dim=1)[0]
    idx = probs.argmax().item()
    return classes[idx], probs[idx].item()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint")
    parser.add_argument("image")
    parser.add_argument("--img-size", type=int, default=224)
    parser.add_argument("--log")
    parser.add_argument("--sector")
    parser.add_argument("--fruit")
    parser.add_argument("--lot", default="")
    args = parser.parse_args()
    if args.log and not (args.sector and args.fruit):
        parser.error("--log requires --sector and --fruit")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, classes = load_model(args.checkpoint, device)
    label, confidence = predict(model, classes, args.image, device, args.img_size)
    print(f"{label} {confidence:.4f}")
    if args.log:
        append_record(args.log, datetime.now(), args.sector, args.fruit, label, confidence, args.lot)


if __name__ == "__main__":
    main()