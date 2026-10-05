import argparse
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms, models


def build_model(num_classes, pretrained=True):
    weights = models.MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
    model = models.mobilenet_v3_small(weights=weights)
    model.classifier[3] = nn.Linear(model.classifier[3].in_features, num_classes)
    return model


def build_loaders(data_dir, img_size=224, batch_size=32):
    train_tf = transforms.Compose([
        transforms.Resize((img_size, img_size)),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    val_tf = transforms.Compose([
        transforms.Resize((img_size, img_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    train_ds = datasets.ImageFolder(f"{data_dir}/train", transform=train_tf)
    val_ds = datasets.ImageFolder(f"{data_dir}/val", transform=val_tf)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    return train_loader, val_loader, train_ds.classes


def train_one_epoch(model, loader, optimizer, criterion, device):
    model.train()
    total_loss = 0.0
    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * images.size(0)
    return total_loss / len(loader.dataset)


@torch.no_grad()
def evaluate(model, loader, criterion, device, num_classes):
    model.eval()
    total_loss = 0.0
    correct = 0
    class_correct = torch.zeros(num_classes)
    class_total = torch.zeros(num_classes)
    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        loss = criterion(outputs, labels)
        total_loss += loss.item() * images.size(0)
        preds = outputs.argmax(1)
        correct += (preds == labels).sum().item()
        for c in range(num_classes):
            mask = labels == c
            class_total[c] += mask.sum().item()
            class_correct[c] += (preds[mask] == c).sum().item()
    n = len(loader.dataset)
    recall = (class_correct / class_total.clamp(min=1)).tolist()
    return total_loss / n, correct / n, recall


def class_weights(train_ds, device):
    counts = torch.zeros(len(train_ds.classes))
    for _, label in train_ds.samples:
        counts[label] += 1
    weights = counts.sum() / (len(counts) * counts)
    return weights.to(device)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--img-size", type=int, default=224)
    parser.add_argument("--out", default="model.pt")
    parser.add_argument("--no-pretrained", action="store_true")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_loader, val_loader, classes = build_loaders(args.data_dir, args.img_size, args.batch_size)
    model = build_model(len(classes), pretrained=not args.no_pretrained).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    weights = class_weights(train_loader.dataset, device)
    criterion = nn.CrossEntropyLoss(weight=weights)

    best_acc = 0.0
    for epoch in range(args.epochs):
        train_loss = train_one_epoch(model, train_loader, optimizer, criterion, device)
        val_loss, val_acc, recall = evaluate(model, val_loader, criterion, device, len(classes))
        recall_str = " ".join(f"{c}={r:.3f}" for c, r in zip(classes, recall))
        print(f"epoch={epoch} train_loss={train_loss:.4f} val_loss={val_loss:.4f} val_acc={val_acc:.4f} recall[{recall_str}]")
        if val_acc > best_acc:
            best_acc = val_acc
            torch.save({"model_state": model.state_dict(), "classes": classes}, args.out)

    print(f"best_val_acc={best_acc:.4f} saved_to={args.out}")


if __name__ == "__main__":
    main()