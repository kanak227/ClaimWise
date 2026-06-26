from __future__ import annotations
import json
import logging
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    f1_score,
    r2_score,
    mean_absolute_error
)
from sklearn.model_selection import train_test_split

from ml.config import MODELS_DIR, FEATURES, DATA_DIR
from ml.pipeline import fraud_score, fraud_label_from_score

logger = logging.getLogger(__name__)


def load_data() -> pd.DataFrame:
    # Check multiple possible dataset locations to support consolidation
    locations = [
        DATA_DIR / "merged_dataset_all.csv",
        DATA_DIR / "merged_dataset.csv",
        Path(__file__).resolve().parent / "fraud_detection_system" / "data" / "merged_dataset_all.csv",
        Path(__file__).resolve().parent / "fraud_detection_system" / "data" / "merged_dataset.csv",
        Path(__file__).resolve().parent / "claims_text_pipeline" / "data" / "labeled_dataset.csv"
    ]
    
    src = None
    for loc in locations:
        if loc.exists():
            src = loc
            break
            
    if not src:
        raise FileNotFoundError("Missing training dataset. Please run preprocess or make sure a dataset is in ml/dataset/")
        
    logger.info(f"Loading training data from {src}")
    df = pd.read_csv(src)
    
    # derive labels/features if not present
    if "fraud_label" not in df.columns and "fraud_flag" in df.columns:
        df["fraud_label"] = df["fraud_flag"]
    elif "fraud_label" not in df.columns:
        df["fraud_label"] = df.apply(lambda r: fraud_label_from_score(fraud_score(r)), axis=1)
        
    if "severity_numeric" not in df.columns:
        sev_col = "severity_level" if "severity_level" in df.columns else "severity"
        if sev_col in df.columns:
            df["severity_numeric"] = df[sev_col].fillna("Low").map({"Low": 1, "Medium": 2, "High": 3, "Low Severity": 1, "Medium Severity": 2, "High Severity": 3})
        else:
            df["severity_numeric"] = 1
            
    if "category" in df.columns:
        cats = sorted(df["category"].dropna().unique().tolist())
        cat_map = {c: i for i, c in enumerate(cats)}
        df["category_id"] = df["category"].map(cat_map).fillna(-1).astype(int)
    else:
        df["category_id"] = 0
        
    return df


def train_fraud(df: pd.DataFrame):
    features = [f for f in FEATURES if f != 'fraud_label']
    X = df[features].fillna(0.0).astype(float)
    y = df['fraud_label'].fillna(0).astype(int)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y if len(y.unique()) > 1 else None)

    clf = RandomForestClassifier(n_estimators=300, random_state=42, class_weight="balanced")
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1_weighted": float(f1_score(y_test, y_pred, average="weighted")),
        "report": classification_report(y_test, y_pred, output_dict=True),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "features": features,
    }
    return clf, metrics


def train_severity(df: pd.DataFrame):
    features = [f for f in FEATURES if f != 'severity_level' and f != 'severity_numeric']
    X = df[features].fillna(0.0).astype(float)
    
    sev_col = "severity_level" if "severity_level" in df.columns else "severity"
    if sev_col not in df.columns:
        df[sev_col] = "Low"
    y = df[sev_col].fillna('Low')

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y if len(y.unique()) > 1 else None)

    clf = RandomForestClassifier(n_estimators=250, random_state=42, class_weight="balanced")
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1_weighted": float(f1_score(y_test, y_pred, average="weighted")),
        "report": classification_report(y_test, y_pred, output_dict=True),
        "confusion_matrix": confusion_matrix(y_test, y_pred, labels=sorted(y.unique())).tolist(),
        "features": features,
        "classes": sorted(list(y.unique())),
    }
    return clf, metrics


def train_complexity(df: pd.DataFrame):
    features = [f for f in FEATURES if f != 'complexity_score']
    X = df[features].fillna(0.0).astype(float)
    y = df['complexity_score'].fillna(1.0).astype(float)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42)

    reg = RandomForestRegressor(n_estimators=300, random_state=42)
    reg.fit(X_train, y_train)

    y_pred = reg.predict(X_test)
    metrics = {
        "r2": float(r2_score(y_test, y_pred)),
        "mae": float(mean_absolute_error(y_test, y_pred)),
        "features": features,
    }
    return reg, metrics


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    df = load_data()
    
    fraud_model, fraud_metrics = train_fraud(df)
    sev_model, sev_metrics = train_severity(df)
    cx_model, cx_metrics = train_complexity(df)

    joblib.dump(fraud_model, MODELS_DIR / "fraud_model.pkl")
    joblib.dump(sev_model, MODELS_DIR / "severity_model.pkl")
    joblib.dump(cx_model, MODELS_DIR / "complexity_model.pkl")
    
    (MODELS_DIR / "metrics.json").write_text(json.dumps({
        "fraud_model": fraud_metrics,
        "severity_model": sev_metrics,
        "complexity_model": cx_metrics,
    }, indent=2))
    
    print("Consolidated training complete. Models saved to:", MODELS_DIR)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
