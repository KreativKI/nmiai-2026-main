"""
Text Classification Baseline -- NM i AI 2026
Sentence-transformers embeddings + logistic regression.

Fast, no GPU needed, strong baseline for most text tasks.

Usage:
    1. Copy to agent-nlp/solutions/bot_v1.py
    2. Update DATA_PATH, TEXT_COL, LABEL_COL
    3. Run: python bot_v1.py
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sentence_transformers import SentenceTransformer
import json
import sys

# === CONFIGURE THESE ===
DATA_PATH = "data/train.csv"
TEST_PATH = "data/test.csv"
TEXT_COL = "text"                       # Column with text data
LABEL_COL = "label"                     # Column with labels
ID_COL = "id"                           # ID column for submission
EMBEDDING_MODEL = "all-MiniLM-L6-v2"   # Fast and good. Alt: all-mpnet-base-v2
N_FOLDS = 5
RANDOM_STATE = 42
OUTPUT_PATH = "predictions.csv"
# ========================


def load_data():
    """Load training data."""
    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} samples")
    print(f"Label distribution:\n{df[LABEL_COL].value_counts()}")
    print(f"Avg text length: {df[TEXT_COL].str.len().mean():.0f} chars")
    return df


def embed_texts(texts, model_name=EMBEDDING_MODEL):
    """Embed texts using sentence-transformers."""
    print(f"Embedding {len(texts)} texts with {model_name}...")
    model = SentenceTransformer(model_name)
    embeddings = model.encode(texts.tolist(), show_progress_bar=True, batch_size=64)
    print(f"Embedding shape: {embeddings.shape}")
    return embeddings, model


def evaluate(X, y):
    """Run cross-validation with multiple classifiers."""
    cv = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)

    classifiers = {
        "LogisticRegression": LogisticRegression(max_iter=1000, random_state=RANDOM_STATE),
        "RandomForest": RandomForestClassifier(n_estimators=200, random_state=RANDOM_STATE),
    }

    results = {}
    for name, clf in classifiers.items():
        scores = cross_val_score(clf, X, y, cv=cv, scoring="accuracy")
        results[name] = scores
        print(f"\n{name}:")
        print(f"  Mean accuracy: {scores.mean():.4f} +/- {scores.std():.4f}")

    # Pick best
    best_name = max(results, key=lambda k: results[k].mean())
    print(f"\nBest: {best_name} ({results[best_name].mean():.4f})")

    return results, classifiers[best_name]


def predict_and_save(clf, X_train, y_train, embed_model):
    """Train on full data and predict test set."""
    clf.fit(X_train, y_train)

    try:
        test_df = pd.read_csv(TEST_PATH)
        X_test = embed_model.encode(test_df[TEXT_COL].tolist(), show_progress_bar=True, batch_size=64)
        predictions = clf.predict(X_test)

        output = pd.DataFrame({
            ID_COL: test_df[ID_COL] if ID_COL in test_df.columns else range(len(predictions)),
            LABEL_COL: predictions,
        })
        output.to_csv(OUTPUT_PATH, index=False)
        print(f"\nPredictions saved to {OUTPUT_PATH}")
    except FileNotFoundError:
        print(f"\nNo test file at {TEST_PATH}. Skipping predictions.")


def main():
    df = load_data()

    # Embed
    X, embed_model = embed_texts(df[TEXT_COL])
    y = df[LABEL_COL].values

    # Evaluate
    results, best_clf = evaluate(X, y)

    # Predict
    predict_and_save(best_clf, X, y, embed_model)

    # Summary for MEMORY.md
    best_name = max(results, key=lambda k: results[k].mean())
    best_score = results[best_name].mean()
    print(f"\n--- For MEMORY.md ---")
    print(f"Approach: {EMBEDDING_MODEL} + {best_name}")
    print(f"CV Accuracy: {best_score:.4f}")
    print(f"Embedding dim: {X.shape[1]}")


if __name__ == "__main__":
    main()
