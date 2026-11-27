"""Reproducible multi-feature LWD proxy calibration and leakage-free validation.

Evaluates four proxy strategies across Italy 7-site (55,550 hourly rows,
Leave-One-Site-Out CV) and Spain DIVINE (8,784 hourly rows, zero-shot external
validation):
  1. rh90_baseline: RH >= 90%
  2. rh_tuned_threshold: fold-tuned RH threshold maximizing F1
  3. dpd_physical_threshold: dew-point depression <= threshold OR rain > 0
  4. multifeature_logistic: L2-regularized logistic regression (IRLS in NumPy)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from lwd_calibration import (  # noqa: E402
    ALL_FEATURE_COLUMNS,
    DEFAULT_LWD_CV_PATH,
    DEFAULT_LWD_MODEL_PATH,
    DEFAULT_LWD_SUMMARY_PATH,
    FEATURE_COLUMNS,
    build_lwd_features,
    predict_lwd_probabilities,
)


ITALY_DIR = (
    PROJECT_DIR.parent
    / "additional data"
    / "raw_data"
    / "leaf_wetness_agromet_italy_2025"
)
DIVINE_HOURLY_PATH = (
    PROJECT_DIR
    / "data"
    / "public_evidence_v0.2"
    / "divine_leaf_wetness_hourly.csv"
)


def _classification_metrics(
    actual: np.ndarray,
    predicted: np.ndarray,
    probs: np.ndarray | None = None,
) -> dict[str, float | int | None]:
    actual_b = actual.astype(bool)
    pred_b = predicted.astype(bool)
    tp = int(np.sum(actual_b & pred_b))
    fp = int(np.sum(~actual_b & pred_b))
    fn = int(np.sum(actual_b & ~pred_b))
    tn = int(np.sum(~actual_b & ~pred_b))
    total = len(actual_b)
    actual_wet = tp + fn
    pred_wet = tp + fp

    sensitivity = tp / actual_wet if actual_wet else 0.0
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    precision = tp / pred_wet if pred_wet else 0.0
    f1 = (
        (2.0 * precision * sensitivity) / (precision + sensitivity)
        if (precision + sensitivity) > 0
        else 0.0
    )
    balanced_accuracy = 0.5 * (sensitivity + specificity)
    agreement = (tp + tn) / total if total else 0.0
    wet_hour_bias_pct = (
        ((pred_wet - actual_wet) / actual_wet) * 100.0 if actual_wet else 0.0
    )
    brier = (
        float(np.mean((probs - actual_b.astype(float)) ** 2))
        if probs is not None
        else None
    )
    return {
        "hourly_n": total,
        "actual_wet_hours": actual_wet,
        "predicted_wet_hours": pred_wet,
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "precision": precision,
        "f1": f1,
        "balanced_accuracy": balanced_accuracy,
        "agreement": agreement,
        "brier_score": brier,
        "wet_hour_bias_pct": wet_hour_bias_pct,
    }


def _best_balanced_threshold(
    scores: np.ndarray,
    actual: np.ndarray,
    candidates: np.ndarray,
    *,
    greater_or_equal: bool = True,
) -> tuple[float, float]:
    best_thresh = float(candidates[0])
    best_bal = -1.0
    actual_b = actual.astype(bool)
    pos_total = float(np.sum(actual_b))
    neg_total = float(np.sum(~actual_b))
    for cand in candidates:
        pred = scores >= cand if greater_or_equal else scores <= cand
        tp = float(np.sum(actual_b & pred))
        tn = float(np.sum(~actual_b & ~pred))
        sens = tp / pos_total if pos_total > 0 else 0.0
        spec = tn / neg_total if neg_total > 0 else 0.0
        bal = 0.5 * (sens + spec)
        if bal > best_bal:
            best_bal = bal
            best_thresh = float(cand)
    return best_thresh, best_bal


def _fit_logistic_irls(
    X_df: pd.DataFrame,
    y: np.ndarray,
    *,
    l2_penalty: float = 5.0,
    max_iter: int = 30,
) -> dict[str, Any]:
    """Fit L2-regularized logistic regression using Newton-Raphson (IRLS)."""
    cols = list(FEATURE_COLUMNS)
    X_raw = X_df[cols].to_numpy(dtype=float)
    means = np.mean(X_raw, axis=0)
    stds = np.std(X_raw, axis=0)
    stds = np.where(stds < 1e-6, 1.0, stds)
    X_std = (X_raw - means) / stds
    X_design = np.column_stack([np.ones(len(X_std), dtype=float), X_std])

    w = np.zeros(X_design.shape[1], dtype=float)
    reg = np.diag([0.0] + [l2_penalty] * len(cols))

    for _ in range(max_iter):
        z = np.clip(X_design @ w, -30.0, 30.0)
        p = 1.0 / (1.0 + np.exp(-z))
        weights_diag = np.maximum(p * (1.0 - p), 1e-6)
        grad = X_design.T @ (p - y) + reg @ w
        hessian = (X_design.T * weights_diag) @ X_design + reg
        step = np.linalg.solve(hessian, grad)
        w = w - step
        if float(np.max(np.abs(step))) < 1e-6:
            break

    train_probs = 1.0 / (1.0 + np.exp(-np.clip(X_design @ w, -30.0, 30.0)))
    prob_thresh, _ = _best_balanced_threshold(
        train_probs, y, np.linspace(0.30, 0.75, 46), greater_or_equal=True
    )

    return {
        "feature_names": cols,
        "scaler_mean": {c: float(m) for c, m in zip(cols, means)},
        "scaler_std": {c: float(s) for c, s in zip(cols, stds)},
        "intercept": float(w[0]),
        "weights": {c: float(val) for c, val in zip(cols, w[1:])},
        "probability_threshold": float(prob_thresh),
    }


def _load_italy_sites() -> list[tuple[str, pd.DataFrame]]:
    site_meta = json.loads((ITALY_DIR / "sites.json").read_text(encoding="utf-8"))
    sites: list[tuple[str, pd.DataFrame]] = []
    for entry in site_meta["sites"]:
        ref = entry["ref"]
        raw = pd.read_csv(ITALY_DIR / ref)
        raw = raw.rename(
            columns={
                "time": "timestamp",
                "temperature": "temperature_c",
                "rh": "rh_pct",
                "rain": "rain_mm",
                "wind_speed": "wind_speed_ms",
            }
        )
        feats = build_lwd_features(raw)
        feats["site_id"] = ref
        feats["leaf_top"] = pd.to_numeric(raw["leaf_top"], errors="coerce")
        feats["leaf_bot"] = pd.to_numeric(raw["leaf_bot"], errors="coerce")
        valid = feats.dropna(subset=list(ALL_FEATURE_COLUMNS) + ["leaf_top", "leaf_bot"]).copy()
        sites.append((ref, valid))
    return sites


def _load_divine_site() -> pd.DataFrame:
    raw = pd.read_csv(DIVINE_HOURLY_PATH)
    raw["wind_speed_ms"] = pd.to_numeric(raw["wind_kmh"], errors="coerce") / 3.6
    feats = build_lwd_features(raw)
    feats["site_id"] = "DIEZMA"
    feats["node1"] = pd.to_numeric(raw["leaf_wetness_minutes_node1"], errors="coerce")
    feats["node2"] = pd.to_numeric(raw["leaf_wetness_minutes_node2"], errors="coerce")
    return feats.dropna(subset=list(ALL_FEATURE_COLUMNS) + ["node1", "node2"]).copy()


def _evaluate_four_models(
    train_df: pd.DataFrame,
    train_target: np.ndarray,
    test_df: pd.DataFrame,
    test_target: np.ndarray,
    *,
    dataset: str,
    validation_split: str,
    site_id: str,
    surface: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    # 1. Fixed RH >= 90% baseline
    pred_rh90 = (test_df["rh_pct"].to_numpy() >= 90.0)
    rows.append(
        {
            "dataset": dataset,
            "validation_split": validation_split,
            "site_id": site_id,
            "surface": surface,
            "model_name": "rh90_baseline",
            "threshold_detail": "RH >= 90%",
            **_classification_metrics(test_target, pred_rh90, pred_rh90.astype(float)),
        }
    )

    # 2. Fold-tuned RH threshold (balanced accuracy to avoid prevalence bias)
    rh_thresh, _ = _best_balanced_threshold(
        train_df["rh_pct"].to_numpy(),
        train_target,
        np.arange(60.0, 96.0, 1.0),
        greater_or_equal=True,
    )
    pred_rh_tuned = (test_df["rh_pct"].to_numpy() >= rh_thresh)
    rows.append(
        {
            "dataset": dataset,
            "validation_split": validation_split,
            "site_id": site_id,
            "surface": surface,
            "model_name": "rh_tuned_threshold",
            "threshold_detail": f"RH >= {rh_thresh:.0f}%",
            **_classification_metrics(
                test_target, pred_rh_tuned, pred_rh_tuned.astype(float)
            ),
        }
    )

    # 3. Physical dew-point depression + rain rule
    # Search DPD threshold assuming rain_mm > 0 is always wet
    best_dpd = 2.0
    best_dpd_bal = -1.0
    tr_dpd = train_df["dew_point_depression_c"].to_numpy()
    tr_rain = train_df["rain_mm"].to_numpy() > 0.0
    for cand in np.arange(0.5, 6.25, 0.25):
        pred_tr = (tr_dpd <= cand) | tr_rain
        m = _classification_metrics(train_target, pred_tr)
        if m["balanced_accuracy"] > best_dpd_bal:
            best_dpd_bal = float(m["balanced_accuracy"])
            best_dpd = float(cand)
    pred_dpd = (test_df["dew_point_depression_c"].to_numpy() <= best_dpd) | (
        test_df["rain_mm"].to_numpy() > 0.0
    )
    rows.append(
        {
            "dataset": dataset,
            "validation_split": validation_split,
            "site_id": site_id,
            "surface": surface,
            "model_name": "dpd_physical_threshold",
            "threshold_detail": f"DPD <= {best_dpd:.2f}C or rain > 0",
            **_classification_metrics(test_target, pred_dpd, pred_dpd.astype(float)),
        }
    )

    # 4. Multi-feature L2 logistic regression (orthogonal physical features)
    model = _fit_logistic_irls(train_df, train_target, l2_penalty=10.0)
    model["dpd_threshold_c"] = float(best_dpd)
    probs, pred_lr = predict_lwd_probabilities(test_df, model=model)
    rows.append(
        {
            "dataset": dataset,
            "validation_split": validation_split,
            "site_id": site_id,
            "surface": surface,
            "model_name": "multifeature_logistic",
            "threshold_detail": f"P >= {model['probability_threshold']:.2f}",
            **_classification_metrics(test_target, pred_lr, probs),
        }
    )
    return rows, model


def run_calibration_experiment() -> dict[str, Any]:
    italy_sites = _load_italy_sites()
    divine_df = _load_divine_site()
    all_rows: list[dict[str, Any]] = []

    # Italy Leave-One-Site-Out Cross-Validation (both leaf_top and leaf_bot)
    for surface in ("leaf_top", "leaf_bot"):
        for held_out_id, test_df in italy_sites:
            train_df = pd.concat(
                [df for sid, df in italy_sites if sid != held_out_id],
                ignore_index=True,
            )
            train_y = (train_df[surface].to_numpy() > 0).astype(float)
            test_y = (test_df[surface].to_numpy() > 0).astype(float)
            fold_rows, _ = _evaluate_four_models(
                train_df,
                train_y,
                test_df,
                test_y,
                dataset="Italy 7-site",
                validation_split="LOSO_CV",
                site_id=held_out_id,
                surface=surface,
            )
            all_rows.extend(fold_rows)

    # Fit frozen model on all 7 Italian sites (leaf_top primary target)
    italy_all = pd.concat([df for _, df in italy_sites], ignore_index=True)
    italy_top_y = (italy_all["leaf_top"].to_numpy() > 0).astype(float)
    _, frozen_model = _evaluate_four_models(
        italy_all,
        italy_top_y,
        italy_all,
        italy_top_y,
        dataset="Italy 7-site",
        validation_split="train_check",
        site_id="ALL_7_SITES",
        surface="leaf_top",
    )

    # Cross-country external validation on Spain DIVINE (node1 & node2)
    for node_col in ("node1", "node2"):
        divine_y = (divine_df[node_col].to_numpy() > 0).astype(float)
        ext_rows, _ = _evaluate_four_models(
            italy_all,
            italy_top_y,
            divine_df,
            divine_y,
            dataset="DIVINE Spain",
            validation_split="external_cross_country",
            site_id="DIEZMA",
            surface=node_col,
        )
        all_rows.extend(ext_rows)

    cv_df = pd.DataFrame(all_rows)
    eval_df = cv_df[cv_df["validation_split"] != "train_check"].copy()
    eval_df.to_csv(DEFAULT_LWD_CV_PATH, index=False, encoding="utf-8-sig")

    summary_df = (
        eval_df.groupby(["dataset", "validation_split", "model_name"], as_index=False)
        .agg(
            comparisons=("site_id", "size"),
            mean_sensitivity=("sensitivity", "mean"),
            std_sensitivity=("sensitivity", "std"),
            mean_specificity=("specificity", "mean"),
            mean_precision=("precision", "mean"),
            mean_f1=("f1", "mean"),
            std_f1=("f1", "std"),
            mean_balanced_accuracy=("balanced_accuracy", "mean"),
            mean_agreement=("agreement", "mean"),
            mean_brier_score=("brier_score", "mean"),
            mean_abs_wet_bias_pct=(
                "wet_hour_bias_pct",
                lambda s: float(np.mean(np.abs(s))),
            ),
        )
        .sort_values(["dataset", "mean_f1"], ascending=[True, False])
    )
    summary_df.to_csv(DEFAULT_LWD_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    italy_summary = summary_df[summary_df["dataset"] == "Italy 7-site"].set_index("model_name")
    spain_summary = summary_df[summary_df["dataset"] == "DIVINE Spain"].set_index("model_name")

    model_payload = {
        "model_version": "lwd_proxy_calib_v0.1",
        "training_dataset": "Italy 7-site Agromet (DOI: 10.17632/sd4b8vpvyb.1, leaf_top > 0)",
        "training_rows": int(len(italy_all)),
        "external_test_dataset": "DIVINE Granada Spain (DOI: 10.5281/zenodo.11432589)",
        "external_test_rows": int(len(divine_df)),
        **frozen_model,
        "validation_summary": {
            "italy_loso_cv": {
                name: {
                    "mean_sensitivity": round(float(row["mean_sensitivity"]), 4),
                    "mean_precision": round(float(row["mean_precision"]), 4),
                    "mean_f1": round(float(row["mean_f1"]), 4),
                    "mean_balanced_accuracy": round(float(row["mean_balanced_accuracy"]), 4),
                    "mean_brier_score": round(float(row["mean_brier_score"]), 4),
                }
                for name, row in italy_summary.iterrows()
            },
            "spain_external": {
                name: {
                    "mean_sensitivity": round(float(row["mean_sensitivity"]), 4),
                    "mean_precision": round(float(row["mean_precision"]), 4),
                    "mean_f1": round(float(row["mean_f1"]), 4),
                    "mean_balanced_accuracy": round(float(row["mean_balanced_accuracy"]), 4),
                    "mean_brier_score": round(float(row["mean_brier_score"]), 4),
                }
                for name, row in spain_summary.iterrows()
            },
        },
        "boundary": (
            "Calibrated meteorological proxy trained on European sites. "
            "Reduces under-detection relative to RH>=90%, but still carries cross-site error "
            "and must not be reported as measured Henan maize canopy LWD or exact infection time."
        ),
    }
    DEFAULT_LWD_MODEL_PATH.write_text(
        json.dumps(model_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "cv_rows": len(eval_df),
        "summary_rows": len(summary_df),
        "model_path": str(DEFAULT_LWD_MODEL_PATH.relative_to(PROJECT_DIR)),
        "validation_summary": model_payload["validation_summary"],
    }


if __name__ == "__main__":
    result = run_calibration_experiment()
    print(json.dumps(result, ensure_ascii=False, indent=2))
