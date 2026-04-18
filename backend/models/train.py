"""
PromptGuard ML Training Script
Trains a TF-IDF + Logistic Regression classifier on the adversarial prompt dataset.

Fixes applied vs. previous version:
- Use word-level n-grams (1,2) instead of char_wb to improve generalisation to unseen phrasings
- Higher max_features (15000) + keep min_df=1 for the small dataset
- Lower regularisation (C=1.0) to reduce overfitting to training surface forms
- Added a character-level TF-IDF column via FeatureUnion so obfuscation is still caught
- Raise decision threshold to 0.60 (serialised with model) to cut false-positive rate
- Balanced class weights already handle the class ratio; augmented dataset does the rest
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import LabelEncoder
from data.dataset import build_dataset

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "saved")
os.makedirs(MODEL_DIR, exist_ok=True)

BINARY_MODEL_PATH  = os.path.join(MODEL_DIR, "binary_classifier.joblib")
CATEGORY_MODEL_PATH = os.path.join(MODEL_DIR, "category_classifier.joblib")
LABEL_ENCODER_PATH  = os.path.join(MODEL_DIR, "label_encoder.joblib")
THRESHOLD_PATH      = os.path.join(MODEL_DIR, "threshold.joblib")

# Decision threshold – calibrated to balance precision / recall.
# Raising this above 0.50 reduces false positives on safe prompts.
DECISION_THRESHOLD = 0.58


def _build_binary_pipeline() -> Pipeline:
    """
    Hybrid TF-IDF: word n-grams for semantics + char n-grams for obfuscation,
    combined via FeatureUnion before the logistic regression head.
    """
    word_tfidf = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        max_features=15000,
        sublinear_tf=True,
        min_df=1,
        token_pattern=r"(?u)\b\w+\b",
    )
    char_tfidf = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        max_features=8000,
        sublinear_tf=True,
        min_df=1,
    )
    features = FeatureUnion([
        ("word", word_tfidf),
        ("char", char_tfidf),
    ])
    clf = LogisticRegression(
        C=1.0,               # lower = more regularisation → less overfitting
        max_iter=2000,
        class_weight="balanced",
        solver="lbfgs",
        random_state=42,
    )
    return Pipeline([("features", features), ("clf", clf)])


def _build_category_pipeline() -> Pipeline:
    tfidf = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        max_features=10000,
        sublinear_tf=True,
        min_df=1,
    )
    clf = LogisticRegression(
        C=1.5,
        max_iter=2000,
        class_weight="balanced",
        solver="lbfgs",
        random_state=42,
    )
    return Pipeline([("tfidf", tfidf), ("clf", clf)])


def train():
    print("Building dataset...")
    df = build_dataset()
    print(f"\nCategory distribution:\n{df['category'].value_counts()}\n")

    # ── Binary Classifier (Safe vs Adversarial) ───────────────────────────────
    print("Training binary classifier...")
    X = df["text"]
    y_binary = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_binary, test_size=0.20, random_state=42, stratify=y_binary
    )

    binary_pipeline = _build_binary_pipeline()
    binary_pipeline.fit(X_train, y_train)

    # Evaluate at the calibrated threshold, not 0.5
    proba_test = binary_pipeline.predict_proba(X_test)[:, 1]
    y_pred = (proba_test >= DECISION_THRESHOLD).astype(int)

    print("\nBinary Classifier Report (threshold=%.2f):" % DECISION_THRESHOLD)
    print(classification_report(y_test, y_pred, target_names=["Safe", "Adversarial"]))
    print("Confusion matrix:\n", confusion_matrix(y_test, y_pred))

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(binary_pipeline, X, y_binary, cv=cv, scoring="f1")
    print(f"Cross-val F1 (default threshold): {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

    # Quick false-positive sanity check on held-out safe prompts
    safe_test = X_test[y_test == 0]
    safe_proba = binary_pipeline.predict_proba(safe_test.tolist())[:, 1]
    fp_rate = (safe_proba >= DECISION_THRESHOLD).mean()
    print(f"False-positive rate on safe test set: {fp_rate:.1%}  (target < 5%)")

    joblib.dump(binary_pipeline, BINARY_MODEL_PATH)
    joblib.dump(DECISION_THRESHOLD, THRESHOLD_PATH)
    print(f"Binary model saved -> {BINARY_MODEL_PATH}")
    print(f"Threshold saved    -> {THRESHOLD_PATH}")

    # ── Category Classifier (Multi-class) ────────────────────────────────────
    print("\nTraining category classifier...")
    df_adv = df[df["label"] == 1].copy()
    le = LabelEncoder()
    y_cat = le.fit_transform(df_adv["category"])

    X_cat_train, X_cat_test, y_cat_train, y_cat_test = train_test_split(
        df_adv["text"], y_cat, test_size=0.20, random_state=42, stratify=y_cat
    )

    category_pipeline = _build_category_pipeline()
    category_pipeline.fit(X_cat_train, y_cat_train)
    y_cat_pred = category_pipeline.predict(X_cat_test)

    print("\nCategory Classifier Report:")
    print(classification_report(y_cat_test, y_cat_pred, target_names=le.classes_))

    joblib.dump(category_pipeline, CATEGORY_MODEL_PATH)
    joblib.dump(le, LABEL_ENCODER_PATH)
    print(f"Category model saved -> {CATEGORY_MODEL_PATH}")
    print(f"Label encoder saved  -> {LABEL_ENCODER_PATH}")

    print("\n[OK] Training complete!")
    return binary_pipeline, category_pipeline, le


if __name__ == "__main__":
    train()
