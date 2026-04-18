"""
PromptGuard ML Classifier
Wraps the trained binary and category classifiers with lazy loading and confidence scoring.

Fixes applied:
- Load the serialised decision threshold (0.58) instead of hardcoding 0.5
  → dramatically reduces false positives on safe prompts
- Graceful fallback when threshold file not found
"""

import os
import joblib
import numpy as np
from dataclasses import dataclass
from typing import Optional

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "saved")
BINARY_MODEL_PATH   = os.path.join(MODEL_DIR, "binary_classifier.joblib")
CATEGORY_MODEL_PATH = os.path.join(MODEL_DIR, "category_classifier.joblib")
LABEL_ENCODER_PATH  = os.path.join(MODEL_DIR, "label_encoder.joblib")
THRESHOLD_PATH      = os.path.join(MODEL_DIR, "threshold.joblib")

DEFAULT_THRESHOLD = 0.58  # conservative default if file missing


@dataclass
class ClassifierResult:
    is_adversarial: bool
    confidence: float          # 0.0 – 1.0 confidence in the adversarial label
    ml_score: float            # raw adversarial probability
    predicted_category: Optional[str]
    category_confidence: float
    model_available: bool


class PromptClassifier:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def _load_models(self):
        if self._loaded:
            return
        try:
            self.binary_model   = joblib.load(BINARY_MODEL_PATH)
            self.category_model = joblib.load(CATEGORY_MODEL_PATH)
            self.label_encoder  = joblib.load(LABEL_ENCODER_PATH)
            # Load calibrated decision threshold
            if os.path.exists(THRESHOLD_PATH):
                self.threshold = float(joblib.load(THRESHOLD_PATH))
            else:
                self.threshold = DEFAULT_THRESHOLD
            self._loaded = True
            print(f"[OK] ML models loaded. Decision threshold: {self.threshold:.2f}")
        except FileNotFoundError:
            print("⚠️  ML models not found — running in rule-only mode.")
            self._loaded = False

    def is_ready(self) -> bool:
        self._load_models()
        return self._loaded

    def reload(self):
        """Force reload of models (e.g. after retraining)."""
        self._loaded = False
        self._load_models()

    def classify(self, text: str) -> ClassifierResult:
        self._load_models()

        if not self._loaded:
            return ClassifierResult(
                is_adversarial=False,
                confidence=0.0,
                ml_score=0.0,
                predicted_category=None,
                category_confidence=0.0,
                model_available=False,
            )

        # Binary classification — use calibrated threshold
        proba = self.binary_model.predict_proba([text])[0]
        adv_probability = float(proba[1])
        is_adversarial = adv_probability >= self.threshold

        # Category classification (only for adversarial)
        predicted_category = None
        category_confidence = 0.0

        if is_adversarial:
            cat_proba = self.category_model.predict_proba([text])[0]
            cat_idx = int(np.argmax(cat_proba))
            category_confidence = float(cat_proba[cat_idx])
            predicted_category = self.label_encoder.inverse_transform([cat_idx])[0]

        return ClassifierResult(
            is_adversarial=is_adversarial,
            confidence=adv_probability,
            ml_score=adv_probability,
            predicted_category=predicted_category,
            category_confidence=category_confidence,
            model_available=True,
        )
