"""Uncertainty-interval decision robustness analysis for `risk_engine.assess`.

Quantifies which management windows remain invariant under realistic public-data
error bounds (e.g., Sentinel-1 revisit uncertainty on flood duration, drainage
delay uncertainty, and gridded reanalysis weather uncertainty) and which inputs
require priority field verification because they flip a decision state.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from itertools import product

from risk_engine import FieldScenario, assess


@dataclass(frozen=True)
class UncertaintyBounds:
    flood_days_delta: float = 0.0
    waterlog_days_delta: float = 0.0
    drainage_delay_delta_hours: float = 0.0
    temperature_delta_c: float = 0.0
    humidity_delta_pct: float = 0.0
    wind_delta_ms: float = 0.0
    vary_standing_water: bool = False
    vary_baseline: bool = False


@dataclass(frozen=True)
class WindowRobustness:
    window: str
    base_status: str
    dominant_status: str
    base_agreement_pct: float
    stability_tier: str
    observed_statuses: tuple[str, ...]
    sensitive_drivers: tuple[str, ...]


@dataclass(frozen=True)
class RobustnessReport:
    total_scenarios: int
    base_risk_label: str
    risk_agreement_pct: float
    observed_risk_labels: tuple[str, ...]
    invariant_window_count: int
    window_results: tuple[WindowRobustness, ...]
    invariant_actions: tuple[str, ...]
    priority_verifications: tuple[str, ...]


def _three_point_grid(
    value: float | None,
    delta: float,
    low_bound: float,
    high_bound: float,
) -> list[float | None]:
    if value is None or delta <= 0.0:
        return [value]
    candidates = [
        round(max(low_bound, value - delta), 3),
        round(value, 3),
        round(min(high_bound, value + delta), 3),
    ]
    deduped: list[float | None] = []
    for item in candidates:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _stability_tier(agreement_pct: float) -> str:
    if agreement_pct >= 99.99:
        return "稳健不变"
    if agreement_pct >= 80.0:
        return "高度稳定"
    return "对误差敏感"


def analyze_robustness(
    base: FieldScenario,
    bounds: UncertaintyBounds,
) -> RobustnessReport:
    """Scan bounded input perturbations around `base` and rank window robustness."""
    base_assessment = assess(base)
    base_windows = {w.window: w.status for w in base_assessment.windows}

    axis_specs: list[tuple[str, str, list[object]]] = [
        (
            "flood_days",
            "连续田面明水天数",
            _three_point_grid(base.flood_days, bounds.flood_days_delta, 0.0, 30.0),
        ),
        (
            "waterlog_days",
            "土壤饱和/渍水天数",
            _three_point_grid(base.waterlog_days, bounds.waterlog_days_delta, 0.0, 30.0),
        ),
        (
            "drainage_delay_hours",
            "排水延迟时间",
            _three_point_grid(
                base.drainage_delay_hours, bounds.drainage_delay_delta_hours, 0.0, 720.0
            ),
        ),
        (
            "temperature_c",
            "日平均温度",
            _three_point_grid(base.temperature_c, bounds.temperature_delta_c, -10.0, 50.0),
        ),
        (
            "humidity_pct",
            "平均相对湿度",
            _three_point_grid(base.humidity_pct, bounds.humidity_delta_pct, 0.0, 100.0),
        ),
        (
            "wind_speed_ms",
            "预计作业风速",
            _three_point_grid(base.wind_speed_ms, bounds.wind_delta_ms, 0.0, 30.0),
        ),
        (
            "standing_water",
            "田面明水状态",
            [False, True]
            if (bounds.vary_standing_water and base.standing_water is not None)
            else [base.standing_water],
        ),
        (
            "pre_flood_baseline",
            "洪涝前病情基线",
            ["none", "sporadic", "established"]
            if bounds.vary_baseline
            else [base.pre_flood_baseline],
        ),
    ]

    active_axes = [(field, label, vals) for field, label, vals in axis_specs if len(vals) > 1]
    if not active_axes:
        combos = [base]
    else:
        combos = []
        fields = [field for field, _, _ in active_axes]
        value_lists = [vals for _, _, vals in active_axes]
        for tup in product(*value_lists):
            updates = dict(zip(fields, tup))
            combos.append(replace(base, **updates))

    assessments = [assess(sc) for sc in combos]
    total = len(assessments)

    risk_counts = Counter(item.risk_label for item in assessments)
    risk_agreement = round((risk_counts[base_assessment.risk_label] / total) * 100.0, 1)

    # One-At-A-Time driver attribution so users know exactly WHICH uncertainty flips each window
    oat_drivers: dict[str, list[str]] = {w.window: [] for w in base_assessment.windows}
    for field, label, vals in active_axes:
        for val in vals:
            if val == getattr(base, field):
                continue
            perturbed = assess(replace(base, **{field: val}))
            for pw in perturbed.windows:
                if pw.status != base_windows[pw.window] and label not in oat_drivers[pw.window]:
                    oat_drivers[pw.window].append(label)

    window_results: list[WindowRobustness] = []
    invariant_actions: list[str] = []
    priority_verifications: list[str] = []
    invariant_count = 0

    for base_win in base_assessment.windows:
        wname = base_win.window
        statuses = [
            next(w.status for w in item.windows if w.window == wname)
            for item in assessments
        ]
        counts = Counter(statuses)
        dominant_status, _ = counts.most_common(1)[0]
        agreement_pct = round((counts[base_win.status] / total) * 100.0, 1)
        tier = _stability_tier(agreement_pct)
        drivers = tuple(oat_drivers[wname])
        if agreement_pct >= 99.99:
            invariant_count += 1
            invariant_actions.append(f"{wname}在全部 {total} 组区间情景下保持不变（{base_win.action}）")
        else:
            driver_text = "、".join(drivers) if drivers else "多因子交互"
            priority_verifications.append(
                f"{wname}在误差区间内一致率为 {agreement_pct:.1f}%，主要受「{driver_text}」影响，建议优先现场核查。"
            )
        window_results.append(
            WindowRobustness(
                window=wname,
                base_status=base_win.status,
                dominant_status=dominant_status,
                base_agreement_pct=agreement_pct,
                stability_tier=tier,
                observed_statuses=tuple(dict.fromkeys(statuses)),
                sensitive_drivers=drivers,
            )
        )

    return RobustnessReport(
        total_scenarios=total,
        base_risk_label=base_assessment.risk_label,
        risk_agreement_pct=risk_agreement,
        observed_risk_labels=tuple(dict.fromkeys(item.risk_label for item in assessments)),
        invariant_window_count=invariant_count,
        window_results=tuple(window_results),
        invariant_actions=tuple(invariant_actions),
        priority_verifications=tuple(priority_verifications),
    )
