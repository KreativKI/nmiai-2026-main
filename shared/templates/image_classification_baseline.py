"""
Image Classification Baseline -- NM i AI 2026
Transfer learning with torchvision (ResNet/EfficientNet).

Usage:
    1. Copy to agent-cv/solutions/bot_v1.py
    2. Update DATA_DIR, NUM_CLASSES, MODEL_NAME
    3. Run: python bot_v1.py

Expects: data/ folder with train/ and test/ subdirectories.
Train: subfolders per class (ImageFolder format) OR a CSV with paths + labels.
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset, random_split
from torchvision import transforms, models
from PIL import Image
import pandas as pd
import numpy as np
import os
import json
from pathlib import Path

# === CONFIGURE THESE ===
DATA_DIR = "data"
TRAIN_CSV = None                    # Set to CSV path if not using ImageFolder
IMAGE_COL = "image_path"            # Column with image paths (if CSV)
LABEL_COL = "label"                 # Column with labels (if CSV)
NUM_CLASSES = 10
MODEL_NAME = "resnet50"             # resnet50 / efficientnet_b0 / mobilenet_v3_small
BATCH_SIZE = 32
NUM_EPOCHS = 10
LEARNING_RATE = 1e-4
IMAGE_SIZE = 224
VAL_SPLIT = 0.2
DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"
OUTPUT_PATH = "predictions.csv"
# ========================


class CSVImageDataset(Dataset):
    """Dataset from CSV file with image paths and labels."""

    def __init__(self, csv_path, transform=None):
        self.df = pd.read_csv(csv_path)
        self.transform = transform
        self.labels = sorted(self.df[LABEL_COL].unique())
        self.label_to_idx = {label: i for i, label in enumerate(self.labels)}

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        image = Image.open(row[IMAGE_COL]).convert("RGB")
        label = self.label_to_idx[row[LABEL_COL]]
        if self.transform:
            image = self.transform(image)
        return image, label


def get_transforms():
    """Train and validation transforms."""
    train_transform = transforms.Compose([
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(10),
        transforms.ColorJitter(brightness=0.2, contrast=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    val_transform = transforms.Compose([
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    return train_transform, val_transform


def get_model():
    """Load pre-trained model and replace classifier head."""
    if MODEL_NAME == "resnet50":
        model = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
        model.fc = nn.Linear(model.fc.in_features, NUM_CLASSES)
    elif MODEL_NAME == "efficientnet_b0":
        model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT)
        model.classifier[1] = nn.Linear(model.classifier[1].in_features, NUM_CLASSES)
    elif MODEL_NAME == "mobilenet_v3_small":
        model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
        model.classifier[3] = nn.Linear(model.classifier[3].in_features, NUM_CLASSES)
    else:
        raise ValueError(f"Unknown model: {MODEL_NAME}")

    return model.to(DEVICE)


def train_one_epoch(model, loader, criterion, optimizer):
    """Train for one epoch."""
    model.train()
    total_loss = 0
    correct = 0
    total = 0

    for images, labels in loader:
        images, labels = images.to(DEVICE), labels.to(DEVICE)

        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * images.size(0)
        _, predicted = outputs.max(1)
        correct += predicted.eq(labels).sum().item()
        total += labels.size(0)

    return total_loss / total, correct / total


def validate(model, loader, criterion):
    """Validate model."""
    model.train(False)
    total_loss = 0
    correct = 0
    total = 0

    with torch.no_grad():
        for images, labels in loader:
            images, labels = images.to(DEVICE), labels.to(DEVICE)
            outputs = model(images)
            loss = criterion(outputs, labels)

            total_loss += loss.item() * images.size(0)
            _, predicted = outputs.max(1)
            correct += predicted.eq(labels).sum().item()
            total += labels.size(0)

    return total_loss / total, correct / total


def main():
    print(f"Device: {DEVICE}")
    print(f"Model: {MODEL_NAME}")

    train_transform, val_transform = get_transforms()

    # Load dataset (train and val get separate transforms to avoid augmentation leak)
    if TRAIN_CSV:
        train_full = CSVImageDataset(TRAIN_CSV, transform=train_transform)
        val_full = CSVImageDataset(TRAIN_CSV, transform=val_transform)
    else:
        from torchvision.datasets import ImageFolder
        train_full = ImageFolder(os.path.join(DATA_DIR, "train"), transform=train_transform)
        val_full = ImageFolder(os.path.join(DATA_DIR, "train"), transform=val_transform)

    # Split into train/val (same indices, different transforms)
    val_size = int(len(train_full) * VAL_SPLIT)
    train_size = len(train_full) - val_size
    generator = torch.Generator().manual_seed(42)
    train_indices, val_indices = random_split(
        range(len(train_full)), [train_size, val_size], generator=generator
    )
    train_dataset = torch.utils.data.Subset(train_full, train_indices.indices)
    val_dataset = torch.utils.data.Subset(val_full, val_indices.indices)

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    print(f"Train: {len(train_dataset)}, Val: {len(val_dataset)}")

    # Model
    model = get_model()
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=LEARNING_RATE)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=NUM_EPOCHS)

    # Train
    best_val_acc = 0
    for epoch in range(NUM_EPOCHS):
        train_loss, train_acc = train_one_epoch(model, train_loader, criterion, optimizer)
        val_loss, val_acc = validate(model, val_loader, criterion)
        scheduler.step()

        print(f"Epoch {epoch+1}/{NUM_EPOCHS}: "
              f"Train Loss={train_loss:.4f} Acc={train_acc:.4f} | "
              f"Val Loss={val_loss:.4f} Acc={val_acc:.4f}")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), "best_model.pth")

    print(f"\nBest validation accuracy: {best_val_acc:.4f}")

    # Summary for MEMORY.md
    print(f"\n--- For MEMORY.md ---")
    print(f"Approach: {MODEL_NAME} transfer learning")
    print(f"Val Accuracy: {best_val_acc:.4f}")
    print(f"Epochs: {NUM_EPOCHS}, LR: {LEARNING_RATE}")


if __name__ == "__main__":
    main()
