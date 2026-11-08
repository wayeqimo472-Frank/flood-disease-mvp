# 田块观测 CSV 字段说明（v0.4）

页面提供空白模板下载。模板只包含表头，不包含示例数据。

每行代表一个田块在一次观测时点的记录。同一 `field_id` 可以出现多行，用于记录不同日期或不同病害观察时点。

## 1. 必填与追踪字段

`field_id` 必填。其余数值和病害字段可以为空；空值进入模型后保留为未知，不按0处理。

建议同时填写：

- `record_id`：记录编号；
- `observation_date`：观测日期；
- `observer`：观测人；
- `county`、`village`、`plot_code`：位置；
- `longitude`、`latitude`：坐标；
- `weather_source`、`flood_source`、`disease_source`：数据来源；
- `evidence_level`：证据等级；
- `notes`：原始记录或缺失原因。

## 2. 进入模型的字段

| 字段 | 含义 | 允许值或单位 |
|---|---|---|
| `crop_stage` | 生育期 | `V3`、`V6`、`VT`、`R3`，可空 |
| `flood_days` | 连续田面明水天数 | 天，可空 |
| `waterlog_days` | 无明水但土壤饱和/渍水天数 | 天，可空 |
| `drainage_delay_hours` | 从淹水开始到排水的时间 | 小时，可空 |
| `standing_water` | 当前田面明水状态 | `yes`、`no`、`unknown` |
| `target_disease` | 目标病害 | `southern_rust`、`stem_rot`、`leaf_spot`、`ear_rot`，可空 |
| `symptom_status` | 当前症状 | `none`、`sparse`、`obvious`，可空 |
| `diagnosis_status` | 诊断状态 | `not_assessed`、`suspected`、`confirmed_fungal`、`confirmed_nonfungal` |
| `pre_flood_baseline` | 洪涝前病情基线 | `unknown`、`none`、`sporadic`、`established` |
| `cultivar_name` | 河南主导品种代码 | 见页面选项，可空 |
| `disease_pressure` | 周边病害压力 | `low`、`moderate`、`high`、`unknown` |
| `temperature_c` | 日平均温度 | ℃，可空 |
| `humidity_pct` | 平均相对湿度 | %，可空 |
| `wind_speed_ms` | 预计作业风速 | m/s，可空 |

## 3. 当前只保存、不参与模型计算的字段

- `flood_start_date`；
- `drainage_date`；
- `max_water_depth_cm`；
- `first_symptom_date`；
- `intervention_summary`；
- `intervention_cost_yuan_per_mu`；
- `yield_kg_per_mu`；
- `yield_loss_pct`。

保留这些字段是为了后续真实数据进入，不表示它们已经进入当前风险计算。

## 4. 输出

每条有效记录输出：

- 数据完整性；
- 处置优先级；
- 明水和渍水状态；
- 环境适宜度；
- 田间证据状态；
- 区域受淹状态；
- 排水窗口和防治窗口状态；
- 缺失输入列表。

E14区域遥感等级当前固定为 `not_available`，不会使用田块明水天数替代。

## 5. 录入边界

- 不使用“溃口合龙日期”代替田块退水日期；
- 不使用区域病情通报代替洪涝前田块基线；
- 不把日平均湿度当作LWD；
- 不把区域遥感像元受淹时长当作田块明水时长；
- 不把试验减产率当作具体农户田块损失；
- 同一田块只有单次观测时，应明确标注，不能伪装成时间序列。
