"""
PromptGuard ML Training Script
Trains a TF-IDF + Logistic Regression classifier on the adversarial prompt dataset.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import LabelEncoder
from data.dataset import build_dataset

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "saved")
os.makedirs(MODEL_DIR, exist_ok=True)

BINARY_MODEL_PATH = os.path.join(MODEL_DIR, "binary_classifier.joblib")
CATEGORY_MODEL_PATH = os.path.join(MODEL_DIR, "category_classifier.joblib")
LABEL_ENCODER_PATH = os.path.join(MODEL_DIR, "label_encoder.joblib")


def train():
    print("Building dataset...")
    df = build_dataset()
    print(f"Dataset size: {len(df)} samples")
    print(df["category"].value_counts())

    # ── Binary Classifier (Safe vs Adversarial) ───────────────────────────────
    print("\nTraining binary classifier...")
    X = df["text"]
    y_binary = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_binary, test_size=0.2, random_state=42, stratify=y_binary
    )

    binary_pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 3),
            max_features=10000,
            sublinear_tf=True,
            min_df=1,
            analyzer="char_wb",  # character n-grams catch obfuscation
        )),
        ("clf", LogisticRegression(
            C=5.0,
            max_iter=1000,
            class_weight="balanced",
            solver="lbfgs",
        )),
    ])

    binary_pipeline.fit(X_train, y_train)
    y_pred = binary_pipeline.predict(X_test)
    print("\nBinary Classifier Report:")
    print(classification_report(y_test, y_pred, target_names=["Safe", "Adversarial"]))

    cv_scores = cross_val_score(binary_pipeline, X, y_binary, cv=5, scoring="f1")
    print(f"Cross-val F1: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

    joblib.dump(binary_pipeline, BINARY_MODEL_PATH)
    print(f"Binary model saved: {BINARY_MODEL_PATH}")

    # ── Category Classifier (Multi-class) ────────────────────────────────────
    print("\nTraining category classifier...")
    df_adv = df[df["label"] == 1].copy()
    le = LabelEncoder()
    y_cat = le.fit_transform(df_adv["category"])

    X_cat_train, X_cat_test, y_cat_train, y_cat_test = train_test_split(
        df_adv["text"], y_cat, test_size=0.2, random_state=42, stratify=y_cat
    )

    category_pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 3),
            max_features=8000,
            sublinear_tf=True,
            analyzer="char_wb",
        )),
        ("clf", LogisticRegression(
            C=3.0,
            max_iter=1000,
            class_weight="balanced",
            solver="lbfgs",
        )),
    ])

    category_pipeline.fit(X_cat_train, y_cat_train)
    y_cat_pred = category_pipeline.predict(X_cat_test)
    print("\nCategory Classifier Report:")
    print(classification_report(y_cat_test, y_cat_pred, target_names=le.classes_))

    joblib.dump(category_pipeline, CATEGORY_MODEL_PATH)
    joblib.dump(le, LABEL_ENCODER_PATH)
    print(f"Category model saved: {CATEGORY_MODEL_PATH}")
    print(f"Label encoder saved: {LABEL_ENCODER_PATH}")

    print("\n[OK] Training complete!")
    return binary_pipeline, category_pipeline, le


if __name__ == "__main__":
    train()
