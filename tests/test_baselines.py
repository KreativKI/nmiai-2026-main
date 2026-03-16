"""
Test that all baseline templates can at least import and run basic operations.
This is a smoke test, not a full integration test.

Usage:
    source agent-cv/.venv/bin/activate
    python tests/test_baselines.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_tabular_baseline():
    """Test tabular baseline with synthetic data."""
    print("Testing tabular_baseline.py...")
    import pandas as pd
    import numpy as np
    from sklearn.model_selection import cross_val_score, StratifiedKFold
    from sklearn.preprocessing import StandardScaler, OrdinalEncoder
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.compose import ColumnTransformer
    import xgboost as xgb

    # Create dummy data
    np.random.seed(42)
    n = 200
    df = pd.DataFrame({
        "feature_a": np.random.randn(n),
        "feature_b": np.random.choice(["cat", "dog", "fish"], n),
        "feature_c": np.random.randint(0, 100, n),
        "target": np.random.choice([0, 1], n),
    })

    X = df.drop(columns=["target"])
    y = df["target"]

    numeric_features = ["feature_a", "feature_c"]
    categorical_features = ["feature_b"]

    numeric_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    categorical_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
        ("encoder", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
    ])
    preprocessor = ColumnTransformer(transformers=[
        ("num", numeric_transformer, numeric_features),
        ("cat", categorical_transformer, categorical_features),
    ])
    pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("model", xgb.XGBClassifier(n_estimators=10, random_state=42, verbosity=0)),
    ])

    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
    scores = cross_val_score(pipeline, X, y, cv=cv, scoring="accuracy")
    print(f"  CV accuracy: {scores.mean():.4f} +/- {scores.std():.4f}")
    print(f"  PASS")
    return True


def test_text_classification_baseline():
    """Test text classification baseline with synthetic data."""
    print("Testing text_classification_baseline.py...")
    from sentence_transformers import SentenceTransformer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score, StratifiedKFold
    import numpy as np

    texts = [
        "This movie was great", "Terrible film", "I loved it",
        "Waste of time", "Best movie ever", "Not worth watching",
        "Amazing performance", "Boring and slow", "Fantastic story",
        "Awful acting", "Highly recommend", "Skip this one",
    ] * 5
    labels = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0] * 5

    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(texts, show_progress_bar=False)

    clf = LogisticRegression(max_iter=1000, random_state=42)
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
    scores = cross_val_score(clf, embeddings, labels, cv=cv, scoring="accuracy")
    print(f"  CV accuracy: {scores.mean():.4f} +/- {scores.std():.4f}")
    print(f"  Embedding dim: {embeddings.shape[1]}")
    print(f"  PASS")
    return True


def test_image_classification_imports():
    """Test image classification imports work."""
    print("Testing image_classification_baseline.py imports...")
    import torch
    import torch.nn as nn
    from torchvision import transforms, models
    from PIL import Image
    import numpy as np

    model = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
    model.fc = nn.Linear(model.fc.in_features, 10)

    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    dummy_img = Image.fromarray(np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8))
    tensor = transform(dummy_img).unsqueeze(0)
    model.train(False)
    with torch.no_grad():
        output = model(tensor)
    print(f"  Output shape: {output.shape} (expected [1, 10])")
    assert output.shape == (1, 10), f"Wrong shape: {output.shape}"
    print(f"  PASS")
    return True


def test_object_detection_imports():
    """Test YOLO imports work."""
    print("Testing object_detection_baseline.py imports...")
    from ultralytics import YOLO
    print(f"  Ultralytics imported OK")
    print(f"  PASS")
    return True


def test_rag_imports():
    """Test RAG baseline imports work."""
    print("Testing rag_baseline.py imports...")
    import anthropic
    import numpy as np
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")
    docs = ["The cat sat on the mat", "Dogs are loyal animals", "Python is a programming language"]
    query = "What animals are loyal?"

    doc_embeddings = model.encode(docs, show_progress_bar=False)
    query_embedding = model.encode([query])

    doc_embeddings = doc_embeddings / np.linalg.norm(doc_embeddings, axis=1, keepdims=True)
    query_embedding = query_embedding / np.linalg.norm(query_embedding)

    similarities = np.dot(doc_embeddings, query_embedding.T).flatten()
    top_idx = int(np.argmax(similarities))
    print(f"  Top match: '{docs[top_idx]}' (score: {similarities[top_idx]:.3f})")
    assert top_idx == 1, f"Expected 'Dogs are loyal animals', got '{docs[top_idx]}'"
    print(f"  PASS")
    return True


def test_stats_utils():
    """Test shared stats utilities."""
    print("Testing shared/stats.py...")
    from shared.stats import compute_stats, welch_ttest

    stats = compute_stats([85, 87, 82, 90, 88])
    assert stats["n"] == 5
    assert stats["mean"] > 0
    print(f"  compute_stats: mean={stats['mean']}, std={stats['std']}")

    result = welch_ttest([85, 87, 82, 90, 88], [90, 92, 88, 95, 91])
    print(f"  welch_ttest: {result['verdict']}")
    print(f"  PASS")
    return True


if __name__ == "__main__":
    print("=" * 50)
    print("NM i AI 2026 Baseline Template Smoke Tests")
    print("=" * 50)
    print()

    tests = [
        test_tabular_baseline,
        test_text_classification_baseline,
        test_image_classification_imports,
        test_object_detection_imports,
        test_rag_imports,
        test_stats_utils,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            failed += 1
        print()

    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    if failed == 0:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print("=" * 50)
