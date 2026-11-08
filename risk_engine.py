from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent / "data"
PRIOR_PATH = DATA_DIR / "model_parameter_priors_v0.2.csv"
RULES_PATH = DATA_DIR / "decision_rules_v0.3.csv"

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
ALLOWED_STAGES = {"V3", "V6", "VT", "R3"}
ALLOWED_SYMPTOMS = {"none", "sparse", "obvious"}
ALLOWED_PRESSURE = {"low", "moderate", "high", "unknown"}
ALLOWED_DISEASES = {"southern_rust", "stem_rot", "leaf_spot", "ear_rot"}
ALLOWED_DIAGNOSIS = {
    "not_assessed",
    "suspected",
    "confirmed_fungal",
    "confirmed_nonfungal",
}
ALLOWED_BASELINE = {"unknown", "none", "sporadic", "established"}
OFFICIAL_CULTIVARS = {
    "unknown",
    "other",
    "MY73",
    "秋乐368",
    "现代959",
    "京科938",
    "郑单958",
    "泛玉298",
    "棒博士767",
    "伟科702",
    "科腾918",
    "鼎诺212",
    "伟科812",
    "浚单1618",
}


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

    def __post_init__(self) -> None:
        if self.crop_stage is not None and self.crop_stage not in ALLOWED_STAGES:
            raise ValueError(f"unsupported crop_stage: {self.crop_stage}")
        if self.target_disease is not None and self.target_disease not in ALLOWED_DISEASES:
            raise ValueError(f"unsupported target_disease: {self.target_disease}")
        if self.symptom_status is not None and self.symptom_status not in ALLOWED_SYMPTOMS:
            raise ValueError(f"unsupported symptom_status: {self.symptom_status}")
        if self.diagnosis_status not in ALLOWED_DIAGNOSIS:
            raise ValueError(f"unsupported diagnosis_status: {self.diagnosis_status}")
        if self.pre_flood_baseline not in ALLOWED_BASELINE:
            raise ValueError(f"unsupported pre_flood_baseline: {self.pre_flood_baseline}")
        if self.cultivar_name not in OFFICIAL_CULTIVARS:
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


@lru_cache(maxsize=1)
def load_priors() -> dict[str, dict[str, str]]:
    with PRIOR_PATH.open(encoding="utf-8-sig", newline="") as file:
        return {row["parameter_id"]: row for row in csv.DictReader(file)}


@lru_cache(maxsize=1)
def load_rules() -> dict[str, dict[str, str]]:
    with RULES_PATH.open(encoding="utf-8-sig", newline="") as file:
        return {row["rule_id"]: row for row in csv.DictReader(file)}


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
) -> str:
    if stage is None or flood_days is None:
        return "unknown"
    if flood_days == 0:
        return "low"

    ten_day_parameter = {
        "V3": "P014",
        "V6": "P015",
        "VT": "P017",
        "R3": "P018",
    }[stage]
    ten_day = _time_value(
        priors,
        ten_day_parameter,
        uses,
        detail=f"{stage}达到10天结果锚点的判断",
    )

    if stage == "V6":
        acceleration_day = _time_value(
            priors,
            "P016",
            uses,
            detail="V6超过6天后的损失加速判断",
        )
        if flood_days >= ten_day:
            return "very_high"
        if flood_days > acceleration_day:
            return "high"
        return "moderate"

    if flood_days >= ten_day:
        return "high"
    return "moderate"


def _waterlogging_band(days: float | None, rules: dict[str, dict[str, str]]) -> str:
    if days is None:
        return "unknown"
    ten_day = _rule_time(rules, "R002")
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
) -> str:
    if days is None:
        return "田面明水天数缺失，未按0天处理"
    if stage is None:
        return f"田面明水{days:g}天；生育期缺失，无法映射阶段证据"
    if days == 0:
        return "无田面明水输入"
    if stage == "R3" and days < _time_value(
        priors,
        "P018",
        uses,
        detail="R3不足10天的状态判断",
    ):
        return f"田面明水{days:g}天；R3不足10天暂无定量锚点，暂不分级"
    if stage in {"V3", "V6", "VT"}:
        duration_boundary = _time_value(
            priors,
            "P013",
            uses,
            detail="不超过4天的状态文字分支",
        )
        loss_upper = float(priors["P013"]["value_high"])
        _record_use(
            uses,
            "P013",
            "解释性证据",
            "value_high",
            "减产上界仅用于解释，不进入风险分数",
        )
        if days <= duration_boundary:
            return (
                f"田面明水{days:g}天；E04仅给出不超过"
                f"{duration_boundary:g}天时减产上界<{loss_upper:g}%，暂不细分"
            )
    if stage == "V6":
        acceleration_day = _time_value(
            priors,
            "P016",
            uses,
            detail="V6超过6天后的状态说明",
        )
        if acceleration_day < days < _time_value(
            priors,
            "P015",
            uses,
            detail="V6 10天致死锚点的状态判断",
        ):
            return f"田面明水{days:g}天；已超过E04的6天损失加速锚点"
    return f"田面明水{days:g}天；存在淹水胁迫，按现有证据仅作粗粒度关注分级"


def _waterlogging_status(
    days: float | None,
    rules: dict[str, dict[str, str]],
) -> str:
    if days is None:
        return "土壤饱和/渍水天数缺失，未按0天处理"
    five_day = _rule_time(rules, "R001")
    ten_day = _rule_time(rules, "R002")
    if days == 0:
        return "无土壤饱和/渍水输入"
    if days < five_day:
        return f"渍水{days:g}天；存在渍水胁迫，但未达到5天最低定量锚点，暂不分级"
    if days < ten_day:
        loss_low = float(rules["R001"]["value_low"])
        loss_high = float(rules["R001"]["value_high"])
        return f"渍水{days:g}天；达到5天产量损失锚点（{loss_low:g}%—{loss_high:g}%）"
    multiplier_low = float(rules["R002"]["value_low"])
    multiplier_high = float(rules["R002"]["value_high"])
    return (
        f"渍水{days:g}天；达到强胁迫比较锚点"
        f"（10天损失为5天的{multiplier_low:g}—{multiplier_high:g}倍）"
    )


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
) -> tuple[tuple[str, ...], tuple[str, ...]]:
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
        known.append("已排除真菌性病害，不评价南方锈病环境适宜度")
    elif suitability == "insufficient_data":
        known.append("温度或湿度缺失，未判断南方锈病环境适宜度")
    elif scenario.target_disease == "southern_rust":
        known.append(f"南方锈病环境适宜度：{ENVIRONMENT_TEXT[suitability]}")
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
    if scenario.target_disease != "southern_rust":
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
) -> str:
    if temperature_c is None or humidity_pct is None:
        return "insufficient_data"
    temp_low = float(rules["R006"]["value_low"])
    temp_high = float(rules["R006"]["value_high"])
    optimal_low = float(rules["R007"]["value_low"])
    optimal_high = float(rules["R007"]["value_high"])
    humidity_threshold = float(rules["R008"]["value_low"])

    in_possible_range = temp_low <= temperature_c <= temp_high
    humid_enough = humidity_pct >= humidity_threshold
    if optimal_low <= temperature_c <= optimal_high and humid_enough:
        return "optimal"
    if in_possible_range and humid_enough:
        return "favorable"
    if in_possible_range or humid_enough:
        return "partial"
    return "unfavorable"


def _pressure_points(scenario: FieldScenario, suitability: str) -> int:
    if scenario.diagnosis_status == "confirmed_nonfungal":
        return 0

    points = 0
    points += scenario.disease_pressure == "high"
    points += 2 if scenario.pre_flood_baseline == "established" else 0
    points += 1 if scenario.pre_flood_baseline == "sporadic" else 0
    points += scenario.symptom_status == "sparse"
    points += 2 if scenario.symptom_status == "obvious" else 0
    if scenario.target_disease == "southern_rust":
        points += 2 if suitability == "optimal" else 0
        points += 1 if suitability == "favorable" else 0
    return points


def _stage_disease_note(scenario: FieldScenario) -> str:
    if scenario.diagnosis_status == "confirmed_nonfungal":
        return "专业诊断已排除真菌性病害，当前不按目标真菌病路径解释。"

    notes: list[str] = []
    if scenario.target_disease == "ear_rot" and scenario.crop_stage != "R3":
        notes.append("穗腐病重点在灌浆成熟期，当前生育期与该病害主要窗口不一致。")
    if scenario.target_disease == "stem_rot" and scenario.crop_stage in {"V3", "V6"}:
        notes.append("茎基腐病多在涝后中后期显症，当前只能做监测与诊断准备。")
    if scenario.target_disease == "southern_rust" and scenario.crop_stage in {"V3", "V6"}:
        notes.append("南方锈病参数主要来自抽雄至灌浆期，早期阶段结论需更保守解释。")
    if scenario.cultivar_name == "郑单958":
        notes.append(
            "郑单958有公开耐涝对比证据，但这不等于其他年份、全部生育期或病害抗性都有定量参数；"
            "系统不据此调整病害风险。"
        )
    elif scenario.cultivar_name not in {"unknown", "other"}:
        notes.append("品种身份已记录，但该主导品种缺少公开耐涝分级，当前不据此调整风险。")
    else:
        notes.append("品种身份未知或为其他品种，当前保留未知状态，不进行品种风险调整。")
    if scenario.pre_flood_baseline == "unknown":
        notes.append("洪涝前病情基线未知，区域通报不能替代田块基线。")
    if not notes:
        notes.append("当前生育期与所选病害没有明显冲突。")
    return " ".join(notes)


def _drainage_decision(scenario: FieldScenario, rules: dict[str, dict[str, str]]) -> WindowDecision:
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
    critical_low = rules["R005"]["value_low"]
    critical_high = rules["R005"]["value_high"]
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
) -> WindowDecision:
    first = _rule_time(rules, "R010")
    second = _rule_time(rules, "R011")
    third = _rule_time(rules, "R012")
    routine = _rule_time(rules, "R013")
    typhoon = _rule_time(rules, "R014")
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
) -> WindowDecision:
    if scenario.diagnosis_status == "confirmed_nonfungal":
        return WindowDecision(
            "病害防治窗口",
            "no_fungicide",
            "已排除真菌性病害，不得用本页结果指导杀菌剂选择。",
            "E004/E8",
        )
    max_wind = float(rules["R016"]["value_central"])
    max_temp = float(rules["R017"]["value_central"])
    recheck_low = rules["R015"]["value_low"]
    recheck_high = rules["R015"]["value_high"]

    if scenario.target_disease == "stem_rot":
        return WindowDecision(
            "病害防治窗口",
            "diagnosis_only",
            "茎基腐病先做监测、取样和病原诊断；当前不给出自动药剂方案。",
            "A2纳入建议；E010安全边界",
        )
    if scenario.target_disease == "ear_rot":
        return WindowDecision(
            "病害防治窗口",
            "harvest_monitoring",
            "穗腐病以灌浆成熟期巡查、降湿和收获管理为主，不由风险分数自动触发用药。",
            "A2/D3/D4",
        )
    if scenario.target_disease == "leaf_spot":
        if scenario.diagnosis_status == "confirmed_fungal":
            return WindowDecision(
                "病害防治窗口",
                "consult_only",
                "已确认真菌性叶斑类病害，但当前没有河南灾后定量参数；药剂和剂量必须以诊断结果、登记标签和当地植保意见为准。",
                "A2/D3/E010",
            )
        if scenario.symptom_status == "none":
            return WindowDecision("病害防治窗口", "monitor", "继续监测，不触发药剂决策。", "A2/D3")
        return WindowDecision(
            "病害防治窗口",
            "pending_diagnosis",
            "叶斑类病害需先区分小斑、弯孢、大斑及其他原因，完成诊断后再咨询当地植保部门。",
            "A2/D3/E008",
        )
    if scenario.diagnosis_status != "confirmed_fungal":
        if scenario.symptom_status is None:
            return WindowDecision(
                "病害防治窗口",
                "data_insufficient",
                "症状状态缺失，无法判断是否需要诊断或防治。",
                "数据完整性检查；E008",
            )
        if scenario.symptom_status == "none":
            if scenario.target_disease == "southern_rust" and suitability in {"optimal", "favorable"} and pressure_points >= 2:
                return WindowDecision(
                    "病害防治窗口",
                    "prepare_early",
                    "尚未显症但环境适宜，提前准备巡查和当地植保咨询；见零星病叶后再诊断和决策。",
                    "E02/D004/D005",
                )
            return WindowDecision("病害防治窗口", "monitor", "继续监测，不触发药剂决策。", "E009")
        return WindowDecision(
            "病害防治窗口",
            "pending_diagnosis",
            "已见疑似症状但尚未确诊，先完成诊断，不能直接推荐杀菌剂。",
            "E008；E4安全合规",
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

    if scenario.target_disease == "southern_rust":
        return WindowDecision(
            "病害防治窗口",
            "open",
            f"已确认真菌性病害且作业条件允许；按登记标签和当地植保意见处置，"
            f"{recheck_low}—{recheck_high}天后复查，不自动开具药剂和剂量。",
            "E02/E011；E010不构成处方",
        )
    return WindowDecision(
        "病害防治窗口",
        "consult_only",
        "当前病种缺少足够的本地定量证据，只能依据诊断结果和当地植保意见决策。",
        "A2/D3",
    )


def _data_completeness(scenario: FieldScenario) -> tuple[str, tuple[str, ...]]:
    core_missing = [
        label
        for value, label in (
            (scenario.crop_stage, "玉米生育期"),
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
    priors = load_priors()
    rules = load_rules()
    parameter_uses: list[ParameterUse] = []

    surface_band = _stage_flood_band(
        scenario.crop_stage,
        scenario.flood_days,
        priors,
        parameter_uses,
    )
    waterlog_band = _waterlogging_band(scenario.waterlog_days, rules)
    surface_water_status = _surface_water_status(
        scenario.crop_stage,
        scenario.flood_days,
        priors,
        parameter_uses,
    )
    waterlogging_status = _waterlogging_status(scenario.waterlog_days, rules)
    field_evidence_status = _field_evidence_status(scenario)
    core_exposure_complete = surface_band != "unknown" and waterlog_band != "unknown"
    base_band = (
        _band_max(surface_band, waterlog_band)
        if core_exposure_complete
        else "unknown"
    )
    # E14 describes independent regional remote-sensing pixels, not field water.
    flood_class = "not_available"
    if scenario.diagnosis_status == "confirmed_nonfungal":
        suitability = "not_applicable"
    elif scenario.target_disease == "southern_rust":
        suitability = _rust_environment_suitability(
            scenario.temperature_c, scenario.humidity_pct, rules
        )
    else:
        suitability = "not_modeled"
    pressure_points = _pressure_points(scenario, suitability)
    high_band = (
        _raise_band(base_band)
        if core_exposure_complete and pressure_points >= 2
        else base_band
    )
    data_completeness, missing_inputs = _data_completeness(scenario)
    known_evidence, unknown_evidence = _known_and_unknown_evidence(
        scenario, surface_water_status, waterlogging_status, suitability
    )

    windows = (
        _drainage_decision(scenario, rules),
        _scouting_decision(scenario, rules),
        _diagnosis_decision(scenario),
        _treatment_decision(scenario, rules, suitability, pressure_points),
    )
    drainage_window = windows[0]
    treatment_window = windows[3]
    monitoring_plan = windows[1].action

    environment_rationale = (
        "已排除真菌性病害，不计算南方锈病环境适宜度"
        if suitability == "not_applicable"
        else "温度或湿度缺失，未判断南方锈病环境适宜度"
        if suitability == "insufficient_data"
        else f"南方锈病环境适宜度为{ENVIRONMENT_TEXT[suitability]}"
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
    if scenario.target_disease != "southern_rust":
        rationale.append("非南方锈病只提供监测、诊断或管理提示，不输出数值病害风险。")

    limitations = [
        "风险区间是证据约束下的筛查分类，不是病害发生概率或精确产量损失。",
        "处置优先级高表示需要优先排水、巡查和诊断，不等于田间已经发病或已经减产。",
        "E02确认早晚期施药存在差异，但公开摘要未给出精确的早期和晚期天数。",
        "E14的3/5/7天是区域遥感分级，不能替代田块实测的退水日期与水深。",
        "E20不能提供可靠的严重度—产量斜率，因此不输出病害驱动的精确减产率。",
        "所有施药建议在诊断、天气、标签和当地植保意见复核前都不得执行。",
        "LWD、田块退水日和田块级洪涝前基线仍缺；主导品种耐涝性和排涝成本只有部分公开证据。",
    ]
    evidence_rule_ids = [
        "R001",
        "R002",
        "R005",
        "R010",
        "R011",
        "R012",
        "R013",
        "R014",
        "R016",
        "R017",
        "R018",
        "R019",
    ]
    if (
        scenario.target_disease == "southern_rust"
        and scenario.diagnosis_status != "confirmed_nonfungal"
        and suitability != "insufficient_data"
    ):
        evidence_rule_ids.extend(("R006", "R007", "R008"))
    if (
        scenario.target_disease == "southern_rust"
        and scenario.diagnosis_status == "confirmed_fungal"
    ):
        evidence_rule_ids.append("R015")
    evidence_parameter_ids = tuple(
        dict.fromkeys(parameter_use.parameter_id for parameter_use in parameter_uses)
    )
    risk_label = (
        "数据不足"
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
        stage_disease_note=_stage_disease_note(scenario),
        windows=windows,
        rationale=tuple(rationale),
        parameter_uses=tuple(parameter_uses),
        evidence_parameter_ids=evidence_parameter_ids,
        evidence_rule_ids=tuple(evidence_rule_ids),
        limitations=tuple(limitations),
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
