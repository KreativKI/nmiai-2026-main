"""
Tabular Data Baseline -- NM i AI 2026
XGBoost + sklearn pipeline for structured/tabular data problems.

Usage:
    1. Copy to agent-{track}/solutions/bot_v1.py
    2. Update DATA_PATH, TARGET_COL, METRIC
    3. Run: python bot_v1.py

Produces: predictions on test set, local CV score.
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import cross_val_score, StratifiedKFold, KFold
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer
from sklearn.metrics import accuracy_score, f1_score, mean_squared_error
import xgboost as xgb
import json
import sys

# === CONFIGURE THESE ===
DATA_PATH = "data/train.csv"           # Path to training data
TEST_PATH = "data/test.csv"            # Path to test data (if separate)
TARGET_COL = "target"                  # Target column name
ID_COL = "id"                          # ID column (for submission)
METRIC = "accuracy"                    # accuracy / f1 / rmse
TASK_TYPE = "classification"           # classification / regression
N_FOLDS = 5
RANDOM_STATE = 42
OUTPUT_PATH = "predictions.csv"
# ========================


def load_data():
    """Load and split data."""
    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} rows, {len(df.columns)} columns")
    print(f"Target distribution:\n{df[TARGET_COL].value_counts()}")
    return df


def build_pipeline(numeric_features, categorical_features):
    """Build sklearn pipeline with preprocessing + XGBoost."""
    numeric_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    categorical_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
        ("encoder", LabelEncoder()),
    ])

    # For categorical, we use OrdinalEncoder instead since LabelEncoder is 1D only
    from sklearn.preprocessing import OrdinalEncoder
    categorical_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
        ("encoder", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
    ])

    preprocessor = ColumnTransformer(transformers=[
        ("num", numeric_transformer, numeric_features),
        ("cat", categorical_transformer, categorical_features),
    ])

    if TASK_TYPE == "classification":
        model = xgb.XGBClassifier(
            n_estimators=500,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=RANDOM_STATE,
            eval_metric="logloss",
        )
    else:
        model = xgb.XGBRegressor(
            n_estimators=500,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=RANDOM_STATE,
        )

    pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("model", model),
    ])

    return pipeline


def evaluate(df):
    """Run cross-validation and return score."""
    X = df.drop(columns=[TARGET_COL] + ([ID_COL] if ID_COL in df.columns else []))
    y = df[TARGET_COL]

    numeric_features = X.select_dtypes(include=["int64", "float64"]).columns.tolist()
    categorical_features = X.select_dtypes(include=["object", "category"]).columns.tolist()

    pipeline = build_pipeline(numeric_features, categorical_features)

    if TASK_TYPE == "classification":
        cv = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)
        scoring = "accuracy" if METRIC == "accuracy" else "f1_weighted"
    else:
        cv = KFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)
        scoring = "neg_root_mean_squared_error"

    scores = cross_val_score(pipeline, X, y, cv=cv, scoring=scoring)

    print(f"\nCV Results ({N_FOLDS}-fold):")
    print(f"  Mean: {scores.mean():.4f}")
    print(f"  Std:  {scores.std():.4f}")
    print(f"  All:  {[f'{s:.4f}' for s in scores]}")

    return scores, pipeline, X, y, numeric_features, categorical_features


def predict_and_save(pipeline, X_train, y_train):
    """Train on full data and predict test set."""
    pipeline.fit(X_train, y_train)

    try:
        test_df = pd.read_csv(TEST_PATH)
        X_test = test_df.drop(columns=[ID_COL] if ID_COL in test_df.columns else [])
        predictions = pipeline.predict(X_test)

        output = pd.DataFrame({
            ID_COL: test_df[ID_COL] if ID_COL in test_df.columns else range(len(predictions)),
            TARGET_COL: predictions,
        })
        output.to_csv(OUTPUT_PATH, index=False)
        print(f"\nPredictions saved to {OUTPUT_PATH}")
    except FileNotFoundError:
        print(f"\nNo test file at {TEST_PATH}. Skipping predictions.")


def main():
    df = load_data()
    scores, pipeline, X, y, num_feats, cat_feats = evaluate(df)

    pipeline_final = build_pipeline(num_feats, cat_feats)
    predict_and_save(pipeline_final, X, y)

    # Summary for MEMORY.md
    print(f"\n--- For MEMORY.md ---")
    print(f"Approach: XGBoost baseline")
    print(f"CV Score ({METRIC}): {scores.mean():.4f} +/- {scores.std():.4f}")
    print(f"Features: {len(num_feats)} numeric, {len(cat_feats)} categorical")


if __name__ == "__main__":
    main()
