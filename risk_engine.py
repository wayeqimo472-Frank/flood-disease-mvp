from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any

from case_pack import DEFAULT_CASE_ID, CasePack, get_case_pack


BAND_ORDER = ("low", "moderate", "high", "very_high")
BAND_LABELS = {
    "low": "低",
    "moderate": "中",
    "high": "高",
    "very_high": "很高",
}
BASELINE_TEXT = {
    "unknown": "未知",
    "none": "未见病害",
    "sporadic": "零星发生",
    "established": "已经普遍发生",
}
ENVIRONMENT_TEXT = {
    "optimal": "适宜",
    "favorable": "可能适宜",
    "partial": "仅部分条件满足",
    "unfavorable": "当前环境不利",
    "not_modeled": "所选病害未建模",
    "not_applicable": "已排除真菌病害",
    "insufficient_data": "数据不足，无法判断",
}
ALLOWED_SYMPTOMS = {"none", "sparse", "obvious"}
ALLOWED_PRESSURE = {"low", "moderate", "high", "unknown"}
ALLOWED_DIAGNOSIS = {
    "not_assessed",
    "suspected",
    "confirmed_fungal",
    "confirmed_nonfungal",
}
ALLOWED_BASELINE = {"unknown", "none", "sporadic", "established"}


@dataclass(frozen=True)
class FieldScenario:
    crop_stage: str | None
    flood_days: float | None
    drainage_delay_hours: float | None
    waterlog_days: float | None = None
    standing_water: bool | None = None
    target_disease: str | None = "southern_rust"
    symptom_status: str | None = "none"
    diagnosis_status: str = "not_assessed"
    pre_flood_baseline: str = "unknown"
    cultivar_name: str = "unknown"
    disease_pressure: str | None = None
    temperature_c: float | None = None
    humidity_pct: float | None = None
    wind_speed_ms: float | None = None
    case_id: str = DEFAULT_CASE_ID

    def __post_init__(self) -> None:
        pack = get_case_pack(self.case_id)
        allowed_stages = set(pack.config["stages"])
        allowed_diseases = set(pack.config["diseases"])
        allowed_cultivars = set(pack.config["cultivars"])
        if self.crop_stage is not None and self.crop_stage not in allowed_stages:
            raise ValueError(f"unsupported crop_stage: {self.crop_stage}")
        if self.target_disease is not None and self.target_disease not in allowed_diseases:
            raise ValueError(f"unsupported target_disease: {self.target_disease}")
        if self.symptom_status is not None and self.symptom_status not in ALLOWED_SYMPTOMS:
            raise ValueError(f"unsupported symptom_status: {self.symptom_status}")
        if self.diagnosis_status not in ALLOWED_DIAGNOSIS:
            raise ValueError(f"unsupported diagnosis_status: {self.diagnosis_status}")
        if self.pre_flood_baseline not in ALLOWED_BASELINE:
            raise ValueError(f"unsupported pre_flood_baseline: {self.pre_flood_baseline}")
        if self.cultivar_name not in allowed_cultivars:
            raise ValueError(f"unsupported cultivar_name: {self.cultivar_name}")
        if self.disease_pressure is not None and self.disease_pressure not in ALLOWED_PRESSURE:
            raise ValueError(f"unsupported disease_pressure: {self.disease_pressure}")
        if self.flood_days is not None and self.flood_days < 0:
            raise ValueError("flood_days and waterlog_days must be non-negative")
        if self.waterlog_days is not None and self.waterlog_days < 0:
            raise ValueError("flood_days and waterlog_days must be non-negative")
        if self.drainage_delay_hours is not None and self.drainage_delay_hours < 0:
            raise ValueError("drainage_delay_hours must be non-negative")
        if self.humidity_pct is not None and not 0 <= self.humidity_pct <= 100:
            raise ValueError("humidity_pct must be between 0 and 100")
        if self.temperature_c is not None and not -20 <= self.temperature_c <= 60:
            raise ValueError("temperature_c must be between -20 and 60")
        if self.wind_speed_ms is not None and self.wind_speed_ms < 0:
            raise ValueError("wind_speed_ms must be non-negative")


@dataclass(frozen=True)
class WindowDecision:
    window: str
    status: str
    action: str
    evidence: str


@dataclass(frozen=True)
class ParameterUse:
    parameter_id: str
    role: str
    field: str
    detail: str


@dataclass(frozen=True)
class Assessment:
    risk_low: str
    risk_high: str
    risk_label: str
    surface_water_status: str
    waterlogging_status: str
    field_evidence_status: str
    known_evidence: tuple[str, ...]
    unknown_evidence: tuple[str, ...]
    data_completeness: str
    missing_inputs: tuple[str, ...]
    regional_flood_class: str
    environment_suitability: str
    drainage_window: str
    disease_window: str
    disease_window_precise_days: str
    monitoring_plan: str
    stage_disease_note: str
    windows: tuple[WindowDecision, ...]
    rationale: tuple[str, ...]
    parameter_uses: tuple[ParameterUse, ...]
    evidence_parameter_ids: tuple[str, ...]
    evidence_rule_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    case_id: str
    region_code: str
    crop_code: str
    case_version: str
    risk_model: str


@lru_cache(maxsize=None)
def load_priors(case_id: str = DEFAULT_CASE_ID) -> dict[str, dict[str, str]]:
    with get_case_pack(case_id).data_file("priors").open(
        encoding="utf-8-sig", newline=""
    ) as file:
        return {row["parameter_id"]: row for row in csv.DictReader(file)}


@lru_cache(maxsize=None)
def load_rules(case_id: str = DEFAULT_CASE_ID) -> dict[str, dict[str, str]]:
    with get_case_pack(case_id).data_file("rules").open(
        encoding="utf-8-sig", newline=""
    ) as file:
        return {row["rule_id"]: row for row in csv.DictReader(file)}


def load_gaps(case_id: str = DEFAULT_CASE_ID) -> dict[str, dict[str, str]]:
    with get_case_pack(case_id).data_file("gaps").open(
        encoding="utf-8-sig", newline=""
    ) as file:
        return {row["gap_id"]: row for row in csv.DictReader(file)}


def _record_use(
    uses: list[ParameterUse] | None,
    parameter_id: str,
    role: str,
    field: str,
    detail: str,
) -> None:
    if uses is None:
        return
    use = ParameterUse(parameter_id, role, field, detail)
    if use not in uses:
        uses.append(use)


def _time_value(
    priors: dict[str, dict[str, str]],
    parameter_id: str,
    uses: list[ParameterUse] | None = None,
    *,
    role: str = "状态判断参数",
    detail: str = "",
) -> float:
    value = priors[parameter_id]["time_value"]
    if not value or value == "unknown":
        raise ValueError(f"{parameter_id} has no numeric time value")
    _record_use(uses, parameter_id, role, "time_value", detail)
    return float(value)


def _rule_time(rules: dict[str, dict[str, str]], rule_id: str) -> float:
    value = rules[rule_id]["time_value"]
    if not value:
        raise ValueError(f"{rule_id} has no numeric time value")
    return float(value)


def _band_max(left: str, right: str) -> str:
    return left if BAND_ORDER.index(left) >= BAND_ORDER.index(right) else right


def _raise_band(band: str, steps: int = 1) -> str:
    index = min(BAND_ORDER.index(band) + steps, len(BAND_ORDER) - 1)
    return BAND_ORDER[index]


def _stage_flood_band(
    stage: str | None,
    flood_days: float | None,
    priors: dict[str, dict[str, str]],
    uses: list[ParameterUse],
    pack: CasePack,
) -> str:
    if stage is None or flood_days is None:
        return "unknown"
    if flood_days == 0:
        return "low"

    stage_parameters = pack.config["stage_parameters"][stage]
    ten_day_parameter = stage_parameters["ten_day"]
    ten_day = _time_value(
        priors,
        ten_day_parameter,
        uses,
        detail=f"{stage}达到10天结果锚点的判断",
    )

    acceleration_parameter = stage_parameters.get("acceleration")
    if acceleration_parameter:
        acceleration_day = _time_value(
            priors,
            acceleration_parameter,
            uses,
            detail=f"{stage}超过加速锚点后的损失判断",
        )
        if flood_days >= ten_day:
            return "very_high"
        if flood_days > acceleration_day:
            return "high"
        return "moderate"

    if flood_days >= ten_day:
        return "high"
    return "moderate"


def _waterlogging_band(
    days: float | None,
    rules: dict[str, dict[str, str]],
    rule_ids: dict[str, str],
) -> str:
    if days is None:
        return "unknown"
    ten_day = _rule_time(rules, rule_ids["ten_day_rule"])
    if days == 0:
        return "low"
    if days < ten_day:
        return "moderate"
    return "high"


def _surface_water_status(
    stage: str | None,
    days: float | None,
    priors: dict[str, dict[str, str]],
    uses: list[ParameterUse],
    pack: CasePack,
) -> str:
    if days is None:
        return "田面明水天数缺失，未按0天处理"
    if stage is None:
        return f"田面明水{days:g}天；生育期缺失，无法映射阶段证据"
    if days == 0:
        return "无田面明水输入"
    stage_parameters = pack.config["stage_parameters"][stage]
    ten_day_parameter = stage_parameters["ten_day"]
    short_duration_parameter = stage_parameters.get("short_duration")
    if short_duration_parameter is None and days < _time_value(
        priors,
        ten_day_parameter,
        uses,
        detail=f"{stage}不足10天的状态判断",
    ):
        return f"田面明水{days:g}天；{stage}不足10天暂无定量锚点，暂不分级"
    if short_duration_parameter:
        duration_boundary = _time_value(
            priors,
            short_duration_parameter,
            uses,
            detail="不超过4天的状态文字分支",
        )
        loss_upper = float(priors[short_duration_parameter]["value_high"])
        _record_use(
            uses,
            short_duration_parameter,
            "解释性证据",
            "value_high",
            "减产上界仅用于解释，不进入风险分数",
        )
        if days <= duration_boundary:
            return (
                f"田面明水{days:g}天；E04仅给出不超过"
                f"{duration_boundary:g}天时减产上界<{loss_upper:g}%，暂不细分"
            )
    acceleration_parameter = stage_parameters.get("acceleration")
    if acceleration_parameter:
        acceleration_day = _time_value(
            priors,
            acceleration_parameter,
            uses,
            detail=f"{stage}超过加速锚点后的状态说明",
        )
        if acceleration_day < days < _time_value(
            priors,
            ten_day_parameter,
            uses,
            detail=f"{stage}十天结果锚点的状态判断",
        ):
            return (
                f"田面明水{days:g}天；"
                f"已超过E04的{acceleration_day:g}天损失加速锚点"
            )
    return f"田面明水{days:g}天；存在淹水胁迫，按现有证据仅作粗粒度关注分级"


def _waterlogging_status(
    days: float | None,
    rules: dict[str, dict[str, str]],
    rule_ids: dict[str, str],
) -> str:
    if days is None:
        return "土壤饱和/渍水天数缺失，未按0天处理"
    five_day_rule = rule_ids["five_day_rule"]
    ten_day_rule = rule_ids["ten_day_rule"]
    five_day = _rule_time(rules, five_day_rule)
    ten_day = _rule_time(rules, ten_day_rule)
    if days == 0:
        return "无土壤饱和/渍水输入"
    if days < five_day:
        return f"渍水{days:g}天；存在渍水胁迫，但未达到5天最低定量锚点，暂不分级"
    if days < ten_day:
        loss_low = float(rules[five_day_rule]["value_low"])
        loss_high = float(rules[five_day_rule]["value_high"])
        return f"渍水{days:g}天；达到5天产量损失锚点（{loss_low:g}%—{loss_high:g}%）"
    multiplier_low = float(rules[ten_day_rule]["value_low"])
    multiplier_high = float(rules[ten_day_rule]["value_high"])
    return (
        f"渍水{days:g}天；达到强胁迫比较锚点"
        f"（10天损失为5天的{multiplier_low:g}—{multiplier_high:g}倍）"
    )


def _generic_surface_water_status(days: float | None) -> str:
    if days is None:
        return "田面明水天数缺失，未按0天处理"
    if days == 0:
        return "无田面明水输入"
    return f"田面明水{days:g}天；当前案例没有本地定量分级，只保留观测值。"


def _generic_waterlogging_status(days: float | None) -> str:
    if days is None:
        return "土壤饱和/渍水天数缺失，未按0天处理"
    if days == 0:
        return "无土壤饱和/渍水输入"
    return f"渍水{days:g}天；当前案例没有本地定量分级，只保留观测值。"


def _field_evidence_status(scenario: FieldScenario) -> str:
    if scenario.diagnosis_status == "confirmed_fungal":
        return "已确认真菌性病害"
    if scenario.diagnosis_status == "confirmed_nonfungal":
        return "已排除真菌性病害"
    if scenario.symptom_status == "obvious":
        return "症状明显，尚未确诊"
    if scenario.symptom_status == "sparse":
        return "零星异常，尚未确诊"
    if scenario.diagnosis_status == "suspected":
        return "已标记疑似，尚未确诊"
    if scenario.symptom_status is None:
        return "症状状态缺失"
    return "尚未发现症状"


def _known_and_unknown_evidence(
    scenario: FieldScenario,
    surface_water_status: str,
    waterlogging_status: str,
    suitability: str,
    pack: CasePack,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    environment_disease_code = pack.config["environment_disease_code"]
    environment_disease_label = pack.config["diseases"][
        environment_disease_code
    ]["short_label"]
    known = [
        surface_water_status,
        waterlogging_status,
        f"田间证据状态：{_field_evidence_status(scenario)}",
    ]
    if scenario.drainage_delay_hours is not None:
        known.append(
            f"从淹水开始到排水的用户输入为{scenario.drainage_delay_hours:g}小时"
        )
    if suitability == "not_applicable":
        known.append(f"已排除真菌性病害，不评价{environment_disease_label}环境适宜度")
    elif suitability == "insufficient_data":
        known.append(f"温度或湿度缺失，未判断{environment_disease_label}环境适宜度")
    elif scenario.target_disease == environment_disease_code:
        known.append(
            f"{environment_disease_label}环境适宜度：{ENVIRONMENT_TEXT[suitability]}"
        )
    else:
        known.append("所选病害尚未建立定量环境适宜度模型")
    if scenario.pre_flood_baseline != "unknown":
        known.append(f"洪涝前病情基线：{BASELINE_TEXT[scenario.pre_flood_baseline]}")
    if scenario.diagnosis_status == "confirmed_nonfungal":
        known.append("已排除真菌性病害，真菌防治路径关闭")

    unknown = [
        "不能据此判断病害发生概率、精确减产率或经济收益",
        "缺少LWD叶面湿润时间，不能用站点湿度代替冠层侵染时长",
    ]
    if scenario.pre_flood_baseline == "unknown":
        unknown.append("缺少洪涝前田块病情基线，无法判断本次涝后病情增量")
    if scenario.target_disease != environment_disease_code:
        unknown.append("所选病种没有本地定量环境模型，不能输出数值病害风险")
    if scenario.symptom_status != "none" and scenario.diagnosis_status not in {
        "confirmed_fungal",
        "confirmed_nonfungal",
    }:
        if scenario.symptom_status is None:
            unknown.append("症状状态缺失，不能判断是否需要取样诊断")
        else:
            unknown.append("疑似症状尚未确诊，不能据此选择药剂或判断病原")
    if scenario.symptom_status == "none":
        unknown.append("当前未见症状不等于未感染，仍需按巡查窗口复核")
    return tuple(known), tuple(unknown)


def _rust_environment_suitability(
    temperature_c: float | None,
    humidity_pct: float | None,
    rules: dict[str, dict[str, str]],
    rule_ids: dict[str, str],
) -> str:
    if temperature_c is None or humidity_pct is None:
        return "insufficient_data"
    temp_low = float(rules[rule_ids["temperature_range"]]["value_low"])
    temp_high = float(rules[rule_ids["temperature_range"]]["value_high"])
    optimal_low = float(rules[rule_ids["optimal_temperature"]]["value_low"])
    optimal_high = float(rules[rule_ids["optimal_temperature"]]["value_high"])
    humidity_threshold = float(rules[rule_ids["humidity_threshold"]]["value_low"])

    in_possible_range = temp_low <= temperature_c <= temp_high
    humid_enough = humidity_pct >= humidity_threshold
    if optimal_low <= temperature_c <= optimal_high and humid_enough:
        return "optimal"
    if in_possible_range and humid_enough:
        return "favorable"
    if in_possible_range or humid_enough:
        return "partial"
    return "unfavorable"


def _pressure_points(
    scenario: FieldScenario,
    suitability: str,
    pack: CasePack,
) -> int:
    if scenario.diagnosis_status == "confirmed_nonfungal":
        return 0

    points = 0
    points += scenario.disease_pressure == "high"
    points += 2 if scenario.pre_flood_baseline == "established" else 0
    points += 1 if scenario.pre_flood_baseline == "sporadic" else 0
    points += scenario.symptom_status == "sparse"
    points += 2 if scenario.symptom_status == "obvious" else 0
    if scenario.target_disease == pack.config["environment_disease_code"]:
        points += 2 if suitability == "optimal" else 0
        points += 1 if suitability == "favorable" else 0
    return points


def _stage_disease_note(scenario: FieldScenario, pack: CasePack) -> str:
    if scenario.diagnosis_status == "confirmed_nonfungal":
        return "专业诊断已排除真菌性病害，当前不按目标真菌病路径解释。"

    notes: list[str] = []
    disease_config = pack.config["diseases"].get(scenario.target_disease or "")
    if disease_config:
        conflict_stages = set(disease_config.get("conflict_stages", ()))
        if scenario.crop_stage in conflict_stages and disease_config.get("stage_note"):
            notes.append(disease_config["stage_note"])

    cultivar_config = pack.config["cultivars"][scenario.cultivar_name]
    if cultivar_config.get("note"):
        notes.append(cultivar_config["note"])
    elif scenario.cultivar_name not in {"unknown", "other"}:
        notes.append("品种身份已记录，但该主导品种缺少公开耐涝分级，当前不据此调整风险。")
    if scenario.pre_flood_baseline == "unknown":
        notes.append("洪涝前病情基线未知，区域通报不能替代田块基线。")
    if not notes:
        notes.append("当前生育期与所选病害没有明显冲突。")
    return " ".join(notes)


def _drainage_decision(
    scenario: FieldScenario,
    rules: dict[str, dict[str, str]],
    rule_ids: dict[str, str],
) -> WindowDecision:
    if scenario.standing_water is True:
        return WindowDecision(
            "排水窗口",
            "active",
            "当前仍有明水，立即开沟、清淤或抽排；先处理低洼深水田块。",
            "E001；排水越早越有利",
        )
    if scenario.flood_days == 0 and scenario.waterlog_days == 0:
        return WindowDecision("排水窗口", "not_applicable", "无淹水或渍水输入，保持常规监测。", "E01/E04")
    if scenario.flood_days is None:
        return WindowDecision(
            "排水窗口",
            "data_insufficient",
            "田面明水天数缺失，无法判断排水窗口；不得按0天处理。",
            "数据完整性检查",
        )
    if scenario.flood_days == 0 and scenario.waterlog_days is None:
        return WindowDecision(
            "排水窗口",
            "data_insufficient",
            "渍水天数缺失，无法判断是否需要排渍散墒；不得按0天处理。",
            "数据完整性检查",
        )
    if scenario.flood_days == 0 and scenario.waterlog_days > 0:
        return WindowDecision(
            "排水窗口",
            "waterlogging_management",
            "明水已退但土壤仍饱和，尽快开沟降湿、中耕散墒，不能把无明水当成无胁迫。",
            "C004；D001",
        )
    critical_rule = rule_ids["drainage_critical"]
    critical_low = rules[critical_rule]["value_low"]
    critical_high = rules[critical_rule]["value_high"]
    if scenario.drainage_delay_hours is None:
        return WindowDecision(
            "排水窗口",
            "data_insufficient",
            "排水时间缺失，无法定位3—4天临界带；请补录实际退水或排水时间。",
            "数据完整性检查",
        )
    if scenario.drainage_delay_hours <= 24:
        status = "open"
        action = "立即排水窗口仍开启，优先完成抢排并记录实际退水时间。"
    elif scenario.drainage_delay_hours <= 72:
        status = "closing"
        action = "排水窗口正在收窄；多个试验的共同临界带为3—4天，但不存在统一的每日损失率。"
    else:
        status = "delayed"
        action = "已超过常用3—4天临界带，转入减损补救并调查根系、倒伏和长势。"
    return WindowDecision(
        "排水窗口",
        status,
        action,
        f"E01/E04；临界带{critical_low}—{critical_high}天，不可换算为逐日损失",
    )


def _scouting_decision(
    scenario: FieldScenario,
    rules: dict[str, dict[str, str]],
    rule_ids: dict[str, str],
) -> WindowDecision:
    first = _rule_time(rules, rule_ids["scouting_first"])
    second = _rule_time(rules, rule_ids["scouting_second"])
    third = _rule_time(rules, rule_ids["scouting_third"])
    routine = _rule_time(rules, rule_ids["scouting_routine"])
    typhoon = _rule_time(rules, rule_ids["scouting_storm"])
    plan = (
        f"排水后{first:g}/{second:g}/{third:g}天巡查；常规每{routine:g}天，"
        f"台风或强降雨后每{typhoon:g}天。"
    )
    if scenario.standing_water is True:
        return WindowDecision("巡查窗口", "blocked_safety", "田面仍有明水，暂不下田；先排水。", "E004；E007")
    if scenario.standing_water is None:
        return WindowDecision(
            "巡查窗口",
            "condition_unknown",
            "当前田面明水状态未知；下田前先确认积水与作业安全，再执行巡查计划。",
            "数据完整性检查；E004",
        )
    return WindowDecision(
        "巡查窗口",
        "scheduled",
        plan + "每次记录水痕、退水日、病叶率、病株率或病情指数。",
        "E007（B级频率）；E017（H级项目流程）",
    )


def _diagnosis_decision(scenario: FieldScenario) -> WindowDecision:
    if scenario.diagnosis_status == "confirmed_fungal":
        return WindowDecision("诊断窗口", "completed_fungal", "已确认真菌性病害，可进入防治决策。", "E004/E008")
    if scenario.diagnosis_status == "confirmed_nonfungal":
        return WindowDecision(
            "诊断窗口",
            "completed_nonfungal",
            "已排除真菌性病害；不得使用杀菌剂方案，应针对细菌、生理或药害另行处理。",
            "E004/E008",
        )
    if scenario.symptom_status is None:
        return WindowDecision(
            "诊断窗口",
            "data_insufficient",
            "症状状态缺失，无法判断是否需要采样诊断；不得视为未见症状。",
            "数据完整性检查；E008",
        )
    if scenario.symptom_status == "none":
        return WindowDecision("诊断窗口", "standby", "尚未发现症状，暂不需要送检。", "E008")
    return WindowDecision(
        "诊断窗口",
        "required",
        "发现疑似症状后先记录部位与形态、取样送检，明确真菌、细菌、生理或药害后再决定用药。",
        "E008；禁止仅凭综合风险分数开药",
    )


def _treatment_decision(
    scenario: FieldScenario,
    rules: dict[str, dict[str, str]],
    suitability: str,
    pressure_points: int,
    pack: CasePack,
    rule_ids: dict[str, str],
) -> WindowDecision:
    if scenario.diagnosis_status == "confirmed_nonfungal":
        return WindowDecision(
            "病害防治窗口",
            "no_fungicide",
            "已排除真菌性病害，不得用本页结果指导杀菌剂选择。",
            "E004/E8",
        )
    disease_config = pack.config["diseases"].get(scenario.target_disease or "")
    if disease_config is None:
        return WindowDecision(
            "病害防治窗口",
            "data_insufficient",
            "目标病害缺失，无法判断防治路径。",
            "数据完整性检查",
        )
    policy = disease_config["treatment_policy"]

    if policy == "diagnosis_only":
        return WindowDecision(
            "病害防治窗口",
            "diagnosis_only",
            disease_config["treatment_action"],
            disease_config["treatment_evidence"],
        )
    if policy == "harvest_monitoring":
        return WindowDecision(
            "病害防治窗口",
            "harvest_monitoring",
            disease_config["treatment_action"],
            disease_config["treatment_evidence"],
        )
    if policy == "consult_only":
        if scenario.diagnosis_status == "confirmed_fungal":
            return WindowDecision(
                "病害防治窗口",
                "consult_only",
                disease_config["confirmed_action"],
                disease_config["confirmed_evidence"],
            )
        if scenario.symptom_status == "none":
            return WindowDecision(
                "病害防治窗口",
                "monitor",
                disease_config["monitor_action"],
                disease_config["monitor_evidence"],
            )
        return WindowDecision(
            "病害防治窗口",
            "pending_diagnosis",
            disease_config["pending_action"],
            disease_config["pending_evidence"],
        )
    if policy != "fungal_open":
        raise ValueError(f"不支持的病害决策策略：{policy}")

    if scenario.diagnosis_status != "confirmed_fungal":
        if scenario.symptom_status is None:
            return WindowDecision(
                "病害防治窗口",
                "data_insufficient",
                "症状状态缺失，无法判断是否需要诊断或防治。",
                "数据完整性检查；E008",
            )
        if scenario.symptom_status == "none":
            if (
                scenario.target_disease == pack.config["environment_disease_code"]
                and suitability in {"optimal", "favorable"}
                and pressure_points >= 2
            ):
                return WindowDecision(
                    "病害防治窗口",
                    "prepare_early",
                    disease_config["prepare_early_action"],
                    disease_config["prepare_early_evidence"],
                )
            return WindowDecision(
                "病害防治窗口",
                "monitor",
                disease_config["monitor_action"],
                disease_config["monitor_evidence"],
            )
        return WindowDecision(
            "病害防治窗口",
            "pending_diagnosis",
            disease_config["pending_action"],
            disease_config["pending_evidence"],
        )

    if scenario.standing_water is True:
        return WindowDecision(
            "病害防治窗口",
            "blocked_water",
            "田面有明水或土壤过湿，暂不具备安全作业条件；先排水。",
            "E004安全合规",
        )
    if scenario.standing_water is None:
        return WindowDecision(
            "病害防治窗口",
            "data_insufficient",
            "当前田面明水状态未知，不能确认是否具备安全作业条件。",
            "数据完整性检查；E004",
        )
    max_wind = float(rules[rule_ids["application_wind"]]["value_central"])
    max_temp = float(rules[rule_ids["application_temperature"]]["value_central"])
    recheck_low = rules[rule_ids["treatment_recheck"]]["value_low"]
    recheck_high = rules[rule_ids["treatment_recheck"]]["value_high"]
    if scenario.wind_speed_ms is None or scenario.temperature_c is None:
        return WindowDecision(
            "病害防治窗口",
            "data_insufficient",
            "作业风速或温度缺失，不能确认施药安全条件；不得按适宜天气处理。",
            "数据完整性检查；E012",
        )
    if scenario.wind_speed_ms > max_wind or scenario.temperature_c > max_temp:
        return WindowDecision(
            "病害防治窗口",
            "blocked_weather",
            f"风速超过{max_wind:g} m/s或温度超过{max_temp:g}℃时暂缓施药，重新选择安全作业时段。",
            "E012",
        )

    return WindowDecision(
        "病害防治窗口",
        "open",
        f"{disease_config['open_action_prefix']}"
        f"{recheck_low}—{recheck_high}{disease_config['open_action_suffix']}",
        disease_config["open_evidence"],
    )


def _data_completeness(
    scenario: FieldScenario,
    pack: CasePack,
) -> tuple[str, tuple[str, ...]]:
    core_missing = [
        label
        for value, label in (
            (scenario.crop_stage, f"{pack.crop_name}生育期"),
            (scenario.flood_days, "连续田面明水天数"),
            (scenario.waterlog_days, "土壤饱和/渍水天数"),
        )
        if value is None
    ]
    auxiliary_missing = [
        label
        for value, label in (
            (scenario.drainage_delay_hours, "排水时间"),
            (scenario.standing_water, "当前田面明水状态"),
            (scenario.target_disease, "目标病害"),
            (scenario.symptom_status, "当前症状"),
            (scenario.disease_pressure, "周边病害压力"),
            (scenario.temperature_c, "日平均温度"),
            (scenario.humidity_pct, "平均相对湿度"),
            (scenario.wind_speed_ms, "预计作业风速"),
        )
        if value is None
    ]
    if scenario.pre_flood_baseline == "unknown":
        auxiliary_missing.append("洪涝前病情基线")
    if scenario.cultivar_name == "unknown":
        auxiliary_missing.append("品种身份")
    if core_missing:
        return "insufficient_core", tuple(core_missing + auxiliary_missing)
    if auxiliary_missing:
        return "partial", tuple(auxiliary_missing)
    return "complete", ()


def _display_number(value: float | None) -> str:
    return "未知" if value is None else f"{value:g}"


def assess(scenario: FieldScenario) -> Assessment:
    pack = get_case_pack(scenario.case_id)
    priors = load_priors(scenario.case_id)
    rules = load_rules(scenario.case_id)
    parameter_uses: list[ParameterUse] = []
    waterlogging_rule_ids = pack.config["waterlogging_parameters"]
    environment_rule_ids = pack.config["environment_rules"]
    rule_ids = pack.config["rule_parameters"]
    environment_disease_code = pack.config["environment_disease_code"]
    environment_disease_label = pack.config["diseases"][
        environment_disease_code
    ]["short_label"]

    risk_model = pack.config.get("risk_model", "quantitative_stage_rules")
    if risk_model == "monitoring_only":
        surface_band = "not_modeled"
        waterlog_band = "not_modeled"
        surface_water_status = _generic_surface_water_status(scenario.flood_days)
        waterlogging_status = _generic_waterlogging_status(scenario.waterlog_days)
    else:
        surface_band = _stage_flood_band(
            scenario.crop_stage,
            scenario.flood_days,
            priors,
            parameter_uses,
            pack,
        )
        waterlog_band = _waterlogging_band(
            scenario.waterlog_days,
            rules,
            waterlogging_rule_ids,
        )
        surface_water_status = _surface_water_status(
            scenario.crop_stage,
            scenario.flood_days,
            priors,
            parameter_uses,
            pack,
        )
        waterlogging_status = _waterlogging_status(
            scenario.waterlog_days,
            rules,
            waterlogging_rule_ids,
        )
    field_evidence_status = _field_evidence_status(scenario)
    core_exposure_complete = surface_band != "unknown" and waterlog_band != "unknown"
    base_band = (
        "not_modeled"
        if risk_model == "monitoring_only"
        else _band_max(surface_band, waterlog_band)
        if core_exposure_complete
        else "unknown"
    )
    # E14 describes independent regional remote-sensing pixels, not field water.
    flood_class = "not_available"
    target_disease_config = pack.config["diseases"].get(
        scenario.target_disease or "",
        {},
    )
    if scenario.diagnosis_status == "confirmed_nonfungal":
        suitability = "not_applicable"
    elif (
        scenario.target_disease == environment_disease_code
        and target_disease_config.get("environment_model")
        == "temperature_humidity"
    ):
        suitability = _rust_environment_suitability(
            scenario.temperature_c,
            scenario.humidity_pct,
            rules,
            environment_rule_ids,
        )
    else:
        suitability = "not_modeled"
    pressure_points = _pressure_points(scenario, suitability, pack)
    high_band = (
        _raise_band(base_band)
        if risk_model != "monitoring_only"
        and core_exposure_complete
        and pressure_points >= 2
        else base_band
    )
    data_completeness, missing_inputs = _data_completeness(scenario, pack)
    known_evidence, unknown_evidence = _known_and_unknown_evidence(
        scenario,
        surface_water_status,
        waterlogging_status,
        suitability,
        pack,
    )

    windows = (
        _drainage_decision(scenario, rules, rule_ids),
        _scouting_decision(scenario, rules, rule_ids),
        _diagnosis_decision(scenario),
        _treatment_decision(
            scenario,
            rules,
            suitability,
            pressure_points,
            pack,
            rule_ids,
        ),
    )
    if risk_model == "monitoring_only" and pack.config.get("monitoring_evidence_label"):
        monitoring_evidence = pack.config["monitoring_evidence_label"]
        windows = tuple(
            WindowDecision(
                window=item.window,
                status=item.status,
                action=item.action,
                evidence=monitoring_evidence,
            )
            for item in windows
        )
    drainage_window = windows[0]
    treatment_window = windows[3]
    monitoring_plan = windows[1].action

    environment_rationale = (
        f"已排除真菌性病害，不计算{environment_disease_label}环境适宜度"
        if suitability == "not_applicable"
        else f"温度或湿度缺失，未判断{environment_disease_label}环境适宜度"
        if suitability == "insufficient_data"
        else f"{environment_disease_label}环境适宜度为{ENVIRONMENT_TEXT[suitability]}"
    )
    rationale = [
        (
            f"田面明水连续{_display_number(scenario.flood_days)}天；"
            f"渍水连续{_display_number(scenario.waterlog_days)}天"
        ),
        surface_water_status,
        waterlogging_status,
        f"生育期{scenario.crop_stage}；情景压力点为{pressure_points}",
        environment_rationale,
        f"洪涝前病情基线为{BASELINE_TEXT[scenario.pre_flood_baseline]}",
    ]
    if scenario.target_disease != environment_disease_code:
        rationale.append(
            f"非{environment_disease_label}只提供监测、诊断或管理提示，"
            "不输出数值病害风险。"
        )

    limitations = list(pack.config["limitations"])
    evidence_rule_ids = list(pack.config["base_evidence_rule_ids"])
    if (
        scenario.target_disease == environment_disease_code
        and target_disease_config.get("environment_model")
        == "temperature_humidity"
        and scenario.diagnosis_status != "confirmed_nonfungal"
        and suitability != "insufficient_data"
    ):
        evidence_rule_ids.extend(environment_rule_ids.values())
    if (
        scenario.target_disease == environment_disease_code
        and scenario.diagnosis_status == "confirmed_fungal"
    ):
        evidence_rule_ids.append(rule_ids["treatment_recheck"])
    evidence_parameter_ids = tuple(
        dict.fromkeys(parameter_use.parameter_id for parameter_use in parameter_uses)
    )
    risk_label = (
        pack.config.get("monitoring_risk_label", "仅监测（未定量校准）")
        if risk_model == "monitoring_only"
        else "数据不足"
        if base_band == "unknown"
        else (
            BAND_LABELS[base_band]
            if base_band == high_band
            else f"{BAND_LABELS[base_band]}—{BAND_LABELS[high_band]}"
        )
    )

    return Assessment(
        risk_low=base_band,
        risk_high=high_band,
        risk_label=risk_label,
        surface_water_status=surface_water_status,
        waterlogging_status=waterlogging_status,
        field_evidence_status=field_evidence_status,
        known_evidence=known_evidence,
        unknown_evidence=unknown_evidence,
        data_completeness=data_completeness,
        missing_inputs=missing_inputs,
        regional_flood_class=flood_class,
        environment_suitability=suitability,
        drainage_window=f"{drainage_window.status}: {drainage_window.action}",
        disease_window=f"{treatment_window.status}: {treatment_window.action}",
        disease_window_precise_days="unknown",
        monitoring_plan=monitoring_plan,
        stage_disease_note=_stage_disease_note(scenario, pack),
        windows=windows,
        rationale=tuple(rationale),
        parameter_uses=tuple(parameter_uses),
        evidence_parameter_ids=evidence_parameter_ids,
        evidence_rule_ids=tuple(evidence_rule_ids),
        limitations=tuple(limitations),
        case_id=pack.case_id,
        region_code=pack.region_code,
        crop_code=pack.crop_code,
        case_version=pack.version,
        risk_model=risk_model,
    )


def demo_scenarios() -> list[dict[str, Any]]:
    scenarios = [
        FieldScenario(
            crop_stage="V6",
            flood_days=2,
            waterlog_days=0,
            drainage_delay_hours=12,
            temperature_c=26,
            humidity_pct=85,
        ),
        FieldScenario(
            crop_stage="V6",
            flood_days=5,
            waterlog_days=3,
            drainage_delay_hours=48,
            disease_pressure="high",
            temperature_c=27,
            humidity_pct=95,
        ),
        FieldScenario(
            crop_stage="V3",
            flood_days=10,
            waterlog_days=7,
            drainage_delay_hours=96,
            symptom_status="sparse",
            diagnosis_status="suspected",
            disease_pressure="high",
            temperature_c=27,
            humidity_pct=95,
        ),
        FieldScenario(
            crop_stage="R3",
            flood_days=10,
            waterlog_days=5,
            drainage_delay_hours=8,
            symptom_status="obvious",
            diagnosis_status="confirmed_fungal",
            disease_pressure="high",
            temperature_c=28,
            humidity_pct=90,
        ),
    ]
    return [asdict(assess(scenario)) for scenario in scenarios]


if __name__ == "__main__":
    print(json.dumps(demo_scenarios(), ensure_ascii=False, indent=2))
