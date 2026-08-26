"""Generate synthetic wearable-sensor data and evaluate activity classifiers."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

SEED = 2026
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"


def generate_data(samples_per_class: int = 1200) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    profiles = {
        "lying": (0.08, 0.04, 0.03, 0.10),
        "sitting": (0.18, 0.08, 0.06, 0.22),
        "standing": (0.30, 0.12, 0.09, 0.38),
        "walking": (1.25, 0.80, 1.60, 1.15),
        "stairs": (1.65, 1.10, 2.25, 1.45),
    }
    frames = []
    for label, (accel, gyro, cadence, energy) in profiles.items():
        n = samples_per_class
        subject = rng.integers(1, 41, n)
        noise = rng.normal(0, 1, (n, 8))
        frame = pd.DataFrame({
            "subject_id": subject,
            "accel_mean": np.maximum(0, accel + noise[:, 0] * (0.08 + accel * 0.10)),
            "accel_std": np.maximum(0, accel * 0.55 + noise[:, 1] * 0.10),
            "gyro_mean": np.maximum(0, gyro + noise[:, 2] * (0.06 + gyro * 0.12)),
            "gyro_std": np.maximum(0, gyro * 0.60 + noise[:, 3] * 0.09),
            "cadence_hz": np.maximum(0, cadence + noise[:, 4] * 0.18),
            "signal_energy": np.maximum(0, energy + noise[:, 5] * 0.14),
            "orientation_change": np.maximum(0, (gyro + accel) * 0.30 + noise[:, 6] * 0.08),
            "spectral_entropy": np.clip(0.25 + accel * 0.22 + noise[:, 7] * 0.07, 0, 1),
            "activity": label,
        })
        frames.append(frame)
    return pd.concat(frames, ignore_index=True).sample(frac=1, random_state=SEED).reset_index(drop=True)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = generate_data()
    df.to_csv(DATA_DIR / "synthetic_activity_windows.csv", index=False)

    features = [c for c in df.columns if c not in {"subject_id", "activity"}]
    train, test = train_test_split(df, test_size=0.25, stratify=df["activity"], random_state=SEED)
    X_train, y_train = train[features], train["activity"]
    X_test, y_test = test[features], test["activity"]

    baseline = DummyClassifier(strategy="most_frequent").fit(X_train, y_train)
    model = Pipeline([
        ("scale", StandardScaler()),
        ("classifier", RandomForestClassifier(n_estimators=250, min_samples_leaf=2, random_state=SEED, n_jobs=-1)),
    ]).fit(X_train, y_train)
    prediction = model.predict(X_test)

    metrics = {
        "project_type": "educational synthetic-data demonstration",
        "seed": SEED,
        "rows": int(len(df)),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "classes": sorted(df["activity"].unique().tolist()),
        "baseline_accuracy": float(accuracy_score(y_test, baseline.predict(X_test))),
        "random_forest_accuracy": float(accuracy_score(y_test, prediction)),
        "random_forest_macro_f1": float(f1_score(y_test, prediction, average="macro")),
    }
    (OUTPUT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    pd.DataFrame(confusion_matrix(y_test, prediction), index=metrics["classes"], columns=metrics["classes"]).to_csv(OUTPUT_DIR / "confusion_matrix.csv")
    (OUTPUT_DIR / "classification_report.txt").write_text(classification_report(y_test, prediction))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
