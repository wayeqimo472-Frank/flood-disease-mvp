# 模块证据卡 v0.1

**生成日期**：2026-11-14（2026-11-15 口径修正）｜ **状态**：**审计草案，未冻结** ｜ **代码状态**：`dev` 分支，`git status --short --branch` 干净，与 `origin/dev` 同步
**审计范围**：只读审计。未修改 `app.py`、`risk_engine.py`、`ui_common.py`、`pages/*`、`case_packs/*`、`data/*`。业务代码未动；另新增只读校验 `tests/test_evidence_cards.py`，并按审计 F19 修正 `README.md` 的数据库说明。
**唯一环境改动**：向项目 `.venv` 安装了 `pypdf`（用于读取漯河论文 PDF 全文；`.venv/` 已在 `.gitignore` 中，仓库无变更）。

---

## 0. 证据等级口径

本卡使用**逐条证据**分级，不使用 A/B/C/D/H 字母等级（字母等级在 `docs/source_selection_v0.1.md` 与外部《00_总览与执行摘要》§5 中有定义，但被项目参数表统一套用，见 `module_audit_v0.1.md` F01）。

| 等级 | 含义 | 本项目当前是否有该级证据 |
|---|---|---|
| `observed_field` | 项目或合作方田块实测 | **无。** 本项目至今没有自有田块观测数据 |
| `public_observed` | 论文、试验站或公开数据库的原始观测 | 有（S01/S16 关联的漯河试验、APSIM Lizaso 试验观测、One Acre Fund、US-CSCAP、DIVINE、意大利 7 站、Flood-Tolerant Maize UAV） |
| `literature_prior` | 同行评审文献中的试验参数或区间 | 有（余卫东 2014、孙静 2025、任佰朝 2014 转引） |
| `official_guidance` | 政府、标准或植保机构技术意见 | 有（DB41/T 2668-2024、国家/省级技术指导意见） |
| `simulated_validation` | 使用官方验证数据完成的仿真 | 有（APSIM MaizeLizaso 涝渍验证情景） |
| `simulated_proxy` | 代理品种或代理土壤下的仿真 | 有（漯河 2021 有界代理情景） |
| `remote_sensed` | 遥感或再分析推算 | 有（E14 河南 7·20 区域分级；NASA POWER 再分析格点） |
| `project_assumption` | 项目显式的人工假设 | 有（巡查 3/7/14 天流程、情景预设、压力点权重、E004/E010 内部规则） |
| `missing` | 当前没有可用数据 | 有（LWD、田块退水日、田块基线、确诊链、逐日水深、成本） |
| `rejected` | 已检查但不能用于该用途 | 有（E20 严重度—产量斜率、E18 大豆 SDS 温室试验） |

**模块关系**（系统内为串行提示，不是概率链）：

```
洪涝暴露 → 作物胁迫与产量影响 → 病害环境适宜性 → 田间症状与诊断证据 → 排水/巡查/诊断/防治窗口
```

> 系统**不**计算 `P(病害) = P(洪涝) × P(易感) × P(气象适宜)`，也不存在同一批田块的联合观测数据可支撑条件概率分解。唯一的多因子合成是 `_pressure_points()` 的**整数加总**（见 M4 卡与审计 F06）。

---

## M1 洪涝暴露

**一句话任务**：判断田块是否受淹、明水与渍水分别持续多久，并据此判断是否需要立即排水。

**科学问题**：田块是否受淹？明水（自由水面）持续多久？无明水的土壤饱和/渍水持续多久？实际退水/排水发生在什么时候？

### 输入字段和单位

| 字段 | 单位 | 取值 | 缺失 | 默认值 | UI 位置 |
|---|---|---|---|---|---|
| `crop_stage` | 枚举 | V3 / V6 / VT / R3 | `None` | `None`（自定义情景） | `pages/2_risk.py:72` |
| `flood_days` | 天（连续田面明水） | 0–30，步长 0.5 | `None` | `None` | `pages/2_risk.py:84` |
| `waterlog_days` | 天（无明水但土壤饱和） | 0–30，步长 0.5 | `None` | `None` | `pages/2_risk.py:95` |
| `drainage_delay_hours` | 小时（淹水开始→排水） | 0–720，步长 6 | `None` | `None` | `pages/2_risk.py:108` |
| `standing_water` | 三态 | yes / no / unknown | `None` | `None` | `pages/2_risk.py:127` |

### 当前计算或判断规则

1. **明水分级**（`risk_engine.py:212 _stage_flood_band`）
   - `flood_days == 0` → `low`；`flood_days is None` → `unknown`
   - 取 `case.json → stage_parameters[stage]` 的 `ten_day`（P014/P015/P017/P018，time_value=10 天）
   - V6 额外取 `acceleration`（P016，6 天）：`flood_days ≥ 10` → `very_high`；`> 6` → `high`；否则 `moderate`
   - V3/VT/R3 无 acceleration：`≥ 10` → `high`；否则 `moderate`
2. **渍水分级**（`risk_engine.py:252 _waterlogging_band`）——按 R001（5 天）、R002（10 天）两条规则的时间值：`0` → `low`；`< 5` → `moderate`；`≥ 5` → `high`
3. **暴露状态文字**（`risk_engine.py:267 _surface_water_status` / `:331 _waterlogging_status`）
   - 缺失时明确写"缺失，未按 0 天处理"
   - V3/V6/VT 且 `days ≤ 4`（P013 time_value）时输出"E04 仅给出不超过 4 天时减产上界 <25%，暂不细分"；25% 仅作文字解释，不进分数
   - 渍水 5–10 天时输出 R001 的 3%–13.8%；≥10 天时输出 R002 的"10 天损失为 5 天的 2.4–3.2 倍"
4. **区域受淹分级**：`risk_engine.py:868` 硬编码 `flood_class = "not_available"`，P019–P021（E14 遥感）**不进入执行路径**（`tests/test_risk_engine.py:393` 断言）

### 输出字段及可能取值

| 输出 | 取值 |
|---|---|
| `surface_water_status` | 自由文本（缺失/无明水/≤4 天上界/超加速锚点/粗粒度关注） |
| `waterlogging_status` | 自由文本 |
| `surface_band` / `waterlog_band`（内部） | low / moderate / high / very_high / unknown |
| `regional_flood_class` | 恒为 `not_available` |
| `data_completeness` | complete / partial / insufficient_core |
| `risk_low` / `risk_high` | 见 M2 卡（暴露是处置优先级的下界） |

### 实际代码位置和函数名

`risk_engine.py:212 _stage_flood_band`、`:252 _waterlogging_band`、`:267 _surface_water_status`、`:331 _waterlogging_status`、`:772 _data_completeness`、`:814 assess`；`case_packs/henan_maize_2026/case.json → stage_parameters / waterlogging_parameters`；参数表 `case_packs/henan_maize_2026/model_parameter_priors_v0.2.csv`（P013–P018）；规则表 `case_packs/henan_maize_2026/decision_rules_v0.3.csv`（R001、R002）。

### 每条证据

| 证据 | 来源 | 等级 | 适用条件 | 不适用条件 |
|---|---|---|---|---|
| P014 V3 淹水 10d 减产≈50% | S03 E04 机构新闻 | `literature_prior` | 河南新乡测坑 3 年，V3，10 天 | 不得作精确估计；不得跨场次插值 |
| P015 V6 淹水 10d 植株死亡（100% 死亡率） | S03 E04 | `literature_prior` | 河南新乡测坑，V6，10 天 | **不得转成减产百分比**；当前被用作 `very_high` 分级锚点（见审计 F07） |
| P016 V6 >6d 损失加速 | S03 E04 | `literature_prior` | 仅 V6 | 不得作 V3/VT/R3 通用阈值 |
| P017 VT 淹水 10d 减产≈50%；P018 R3 10d 减产>20% | S03 E04 | `literature_prior` | 河南新乡测坑 | 20% 为下界，不是上限 |
| P013 淹水 ≤4d 减产上界 <25% | S03 E04 | `literature_prior` | V3/V6/VT | 25% 仅解释性，不进分数 |
| R001 渍水 5d 减产 3%–13.8%；R002 10d 为 5d 的 2.4–3.2 倍 | S05 C004 余卫东 2014 | `literature_prior` | **安徽合肥**、V6、浚单20、无明水渍水、90% 田间持水量、3 重复 | 不得称河南通用；不得折算成淹水天数；不得把倍数乘上界当精确损失 |
| P019–P021 连续淹水 3/5/≥7 天分级 | S04 E14 遥感 | `remote_sensed` | 2021 河南 7·20 **区域像元** | 不得当田块明水天数；不得当实测水深；当前未进入执行路径 |
| R005 排水 3–4 天共同临界带 | S15 E005 证据矩阵 | `project_assumption`（多来源综合，非单次试验） | 用于排水窗口状态分支 | 不得换算逐日损失率 |

### 能回答什么

- 这次情景的明水/渍水**持续时间**落在哪一档、粗粒度关注级别如何；
- 是否处于"明水未退"或"明水已退但土壤仍饱和"的作业限制状态；
- 是否还来得及排水（排水窗口，M5）。

### 不能回答什么

- 田块实际淹了多深（系统无水深输入）；
- 明水什么时候开始/结束、几点退水（只有用户手填的 `drainage_delay_hours`）；
- 涝渍与减产的定量关系（系统不输出减产率）；
- 区域遥感受淹分级（无独立像元数据，恒为"暂无"）；
- 先涝后渍的组合胁迫效应（G006，全文未取得）。

### 数据缺失时的行为

- `flood_days` / `waterlog_days` / `crop_stage` 任一为 `None` → `insufficient_core`，处置优先级显示"数据不足"；
- **不以 0 代替缺失**：`risk_engine.py:220/259` 分别返回 `unknown` 与"未按 0 天处理"文案；
- `drainage_delay_hours` 缺失只影响排水窗口（`data_insufficient`），不影响暴露分级；
- 巡查窗口在 `standing_water is None` 时返回"作业条件未知"，不假设安全。

### 当前数据缺口

`data/all_missing_data_v0.3.csv`：M011 明水开始时间、M012 明水结束/退水时间、M013 最大积水深度、M014 逐日水深序列、M015 明水与饱和状态分开、M016 排水起止时间、M017 积水面积比例、M004/M005/M006 土壤与排水条件、M047/M048 田块边界与 SAR 掩膜。

### 是否已实现

**部分实现。** 暴露分级、状态文字、缺失处理已实现并有单元测试；深度、时间序列、区域分级未实现。

### 下一步最小行动

1. 把 `flood_days` 拆成 `flood_start_datetime` / `flood_end_datetime` / `drainage_datetime` 三个可空字段（先只加字段、不改算法）；
2. 在 `data/field_observation_template_v0.6.csv` 已有的 `flood_start_date`/`drainage_date`/`max_water_depth_cm` 之外，补"逐日水位记录"最小记录单元；
3. 给 priors 表加 `current_use` 列，显式标出 P019–P021 未进入执行路径（现状只靠测试断言）。

---

## M2 作物胁迫与产量影响

**一句话任务**：在给定生育期、淹水历时、排水延迟和品种条件下，界定作物胁迫等级与可引用的产量损失区间，并标出该结论的适用边界。

**科学问题**：在给定生育期、淹水历时、排水延迟和作物品种下，作物可能受到多大影响？哪些生育期最敏感？

### 输入字段和单位

| 字段 | 单位 | 取值 | 缺失 | 默认值 | 是否真正参与计算 |
|---|---|---|---|---|---|
| `crop_stage` | 枚举 | V3/V6/VT/R3 | `None` | `None` | **是**（选 ten_day/acceleration 锚点） |
| `flood_days` | 天 | 0–30 | `None` | `None` | **是** |
| `waterlog_days` | 天 | 0–30 | `None` | `None` | **是**（R001/R002） |
| `drainage_delay_hours` | 小时 | 0–720 | `None` | `None` | 仅进 M5 排水窗口，M2 不算 |
| `cultivar_name` | 枚举（12 个河南主栽品种 + unknown/other） | — | `None` | `"unknown"` | **否**。只记录身份、只出文字提示（`risk_engine.py:491 _stage_disease_note`；郑单958 有"有公开耐涝对比"提示但不改分数） |

### 当前计算或判断规则

**系统不输出任何产量损失数字。** 产量相关的数值只以两种形式出现：

1. **文字说明**（`risk_engine.py:267` / `:331`）
   - ≤4 天明水 → "E04 仅给出不超过 4 天时减产上界 <25%"（P013 `value_high`，标为"解释性证据"，不进分数）
   - 渍水 5–10 天 → "达到 5 天产量损失锚点（3%–13.8%）"（R001）
   - 渍水 ≥10 天 → "10 天损失为 5 天的 2.4–3.2 倍"（R002）
2. **关注分级**（`risk_engine.py:212`）——用 P014–P018 的 10 天锚点与 P016 的 6 天加速锚点把 `flood_days` 映射到 low/moderate/high/very_high，再由 `assess()` 汇总为"处置优先级"区间。

**P001–P004（漯河排水延迟 21.28%、追氮 +8.07% 等）当前完全不参与计算**，代码与 case.json 中均无引用（只有 CSV 里存在）。

### 输出字段及可能取值

| 输出 | 取值 | 说明 |
|---|---|---|
| 胁迫/关注等级（内部 `base_band`） | low / moderate / high / very_high / unknown / not_modeled | 是**管理关注分类**，不是减产率 |
| `risk_label` | 低 / 中 / 高 / 很高 / "低—中" 等区间 / "数据不足" / "仅监测（未定量校准）" | 处置优先级，非概率、非减产 |
| `surface_water_status` / `waterlogging_status` | 自由文本 | 含上述产量锚点的限定表述 |
| `stage_disease_note` | 自由文本 | 生育期—病害冲突 + 品种提示 |

### 实际代码位置和函数名

`risk_engine.py:212 _stage_flood_band`、`:267 _surface_water_status`、`:331 _waterlogging_status`、`:491 _stage_disease_note`、`:814 assess`（`:889` 压力点升档逻辑）。

### 每条证据

| 证据 | 来源 | 等级 | 适用条件 | 不适用条件 |
|---|---|---|---|---|
| P013–P018 | S03 E04 机构新闻（**二次来源，非同行评审**） | `literature_prior` | 河南新乡 3 年测坑；V3/V6/VT/R3；淹水 10 天量级 | 不得生成逐日减产率；不得作精确平均；不得跨生育期插值 |
| R001/R002 | S05 C004 余卫东 2014 | `literature_prior` | 安徽合肥、V6、浚单20、渍水（无明水） | 不得称河南通用损失率 |
| P001–P004 | S01 闫振华 2023 漯河试验 | `public_observed` | 河南漯河、**孕穗期**、2021-07-18–21 降雨 185.60 mm、5 处理、CK 5 天后无明水且绝产 | **当前未进入任何计算**；不得转成病害效应；不得跨生育期外推 |
| Lizaso 1991 产量对照（模拟 vs 观测） | S17 APSIM 官方验证情景 | `simulated_validation` | 官方验证数据集、1991、特定地点土壤与品种 | 不代表河南；4 天情景模型低估产量损失：减产率相差 16.85 与 19.91 个百分点（-28.53% vs -45.38%；-28.75% vs -48.66%），模拟产量相对观测产量偏高 26.28% 与 33.94%（见审计 F08） |
| 漯河 2021 有界代理 | S16 本项目代理仿真 | `simulated_proxy` | 代理品种（APSIM DeKalb 模型） | **不是 ZYY432/DK517 的参数校准**；不得用于河南产量预测 |
| 情景预设（`case.json scenario_presets`） | S24 | `project_assumption` | 演示用 | 页面已标注"情景假设值，非田间实测" |

### 能回答什么

- 在当前生育期与淹水历时下，**管理上需要关注到什么程度**；
- 哪些生育期—淹水组合在既有公开试验中被描述为极端（死亡/绝收/近 50% 减产）以及其**严格适用条件**；
- 同一组输入下，结论是"关注分级高"而不是"会减产 50%"。

### 不能回答什么

- 本田块的减产率、产量损失区间或产量预测（系统不输出、也不做外推）；
- 品种耐涝性对胁迫等级或产量的量化影响（无任何品种参数进入计算）；
- 涝渍 × 追肥 × 排水组合的联合效应；
- 病害驱动的产量损失（E20 的严重度—产量斜率已核验为不可用，见 `rejected`）。

### 数据缺失时的行为

- 核心三项（生育期/明水/渍水）缺失 → 优先级"数据不足"，不降级为低风险；
- `cultivar_name == "unknown"` → 追加"品种身份缺失"到 `missing_inputs`，但**不影响**任何分级（这是正确的：品种缺失不能使胁迫判断失效）；
- `pre_flood_baseline == "unknown"` → 追加到缺失清单。

### 当前数据缺口

M039/M040（实收产量、配对对照田产量）、M002（受淹—未受淹配对编号）、M008/M010（播种日期、每次观测生育期）、M009（品种唯一身份）、M037（追肥/中耕/扶正等恢复措施记录）、M011–M016（暴露时间序列）、G004（2020s 主栽品种耐涝性）、G006（先涝后渍组合胁迫）。

### 是否已实现

**部分实现。** 关注分级与限定性文字已实现；产量损失区间输出**未实现**（有意为之）。

### 下一步最小行动

1. **不改算法**，先在 `model_parameter_priors_v0.2.csv` 加 `current_use` 列，把 P001–P004 标成"未进入执行路径（备查）"；
2. 把 P001–P004 与 P005–P012 的 **evidence_level 从统一的 B 拆开**（见审计 F01）；
3. 在 `data/field_observation_template_v0.6.csv` 增加"配对对照田 ID"与"减产率计算公式"两列，为将来做真实减产率留接口；
4. 不新增任何产量预测输出。

---

## M3 病害环境适宜性

**一句话任务**：判断退水后的温度、湿度条件（以及已知的其他必要条件）是否落在目标病害的已知适宜范围内，并列出支撑与缺失的参数。

**科学问题**：退水后的温度、湿度、叶面湿润条件和菌源条件是否适合目标病害发展？

### 输入字段和单位

| 字段 | 单位 | 取值 | 缺失 | 默认值 | UI 位置 |
|---|---|---|---|---|---|
| `temperature_c` | ℃（日平均） | UI 0–45，引擎校验 −20–60 | `None` | `None` | `pages/2_risk.py:223` |
| `humidity_pct` | %（平均相对湿度） | 0–100 | `None` | `None` | `pages/2_risk.py:234` |
| `target_disease` | 枚举 | southern_rust / stem_rot / leaf_spot / ear_rot | `None` | `None` | `pages/2_risk.py:145` |
| `disease_pressure` | 枚举 | low/moderate/high/unknown | `None` | `None` | `pages/2_risk.py:208` |

**LWD（叶面湿润时间）、逐小时温湿度、冠层微气象、初始菌源量均为缺失项，系统没有对应输入字段。**

### 当前计算或判断规则

`risk_engine.py:446 _rust_environment_suitability`（**仅对 `southern_rust` 且 `environment_model == "temperature_humidity"` 生效**）：

```
若 temperature_c 或 humidity_pct 任一为 None          → insufficient_data
possible = 15 ≤ T ≤ 31                    (R006)
optimal  = 24 ≤ T ≤ 28                    (R007)
humid    = RH ≥ 90                        (R008)
optimal 且 humid → optimal
possible 且 humid → favorable
possible 或 humid → partial
否则 → unfavorable
```

`risk_engine.py:873`：`diagnosis_status == "confirmed_nonfungal"` 时直接 `not_applicable`（关闭真菌环境评价）。
`risk_engine.py:880`：目标病害不是南方锈病 → `not_modeled`。

### 输出字段及可能取值

`environment_suitability` ∈ `optimal`（适宜）/ `favorable`（可能适宜）/ `partial`（部分满足）/ `unfavorable`（不利）/ `not_modeled`（未建模）/ `not_applicable`（已排除真菌病害）/ `insufficient_data`（数据不足）。

**该字段不是病害发生概率。**

### 实际代码位置和函数名

`risk_engine.py:446 _rust_environment_suitability`、`:471 _pressure_points`、`:814 assess`（`:873–887` 适宜度分支）；规则表 R006/R007/R008；`case_packs/henan_maize_2026/case.json → environment_rules / environment_disease_code`；`pages/5_evidence.py:206–224` 展示 RH≥90% 代理与真实 LWD 的比较表。

### 每条证据

| 证据 | 来源 | 等级 | 适用条件 | 不适用条件 |
|---|---|---|---|---|
| R006 温度可能范围 15–31℃ | S06 DB41/T 2668-2024 附录 A.2 | `official_guidance` | 玉米南方锈病 | 不得称侵染阈值 |
| R007 最适温度 24–28℃ | S07 国家玉米南方锈病防控技术指导意见（2023-11-29） | `official_guidance` | 玉米南方锈病 | 不得换算成侵染概率 |
| R008 RH ≥ 90% 高湿触发 | S06 DB41/T 2668-2024 附录 A.2 | `official_guidance` | 监测触发 | **不得反推叶面湿润时长** |
| RH≥90% 代理的真实表现 | S20（基于 S18 DIVINE 8784 h + S19 意大利 7 站 55,550 h 汇总） | `public_observed`（派生自公开观测） | 站点级微气象，作物/病害标签缺失 | 平均敏感度 0.42 / 0.35 → **漏报严重**；站点气候与作物不同，不可外推为玉米冠层结论 |
| 5–6 天潜育期（R009） | S08 广西农业农村厅 | `official_guidance` | 河南南方锈病侵染→显症 | **代码刻意未采用**（`tests/test_risk_engine.py:394`）；不得加到洪涝日期上 |
| 菌源条件（`disease_pressure`） | 用户录入 | `project_assumption` | 无独立来源 | 无数据来源支撑，仅作压力点计分 |

### 能回答什么

- 在给定日均温和平均湿度下，**已知适宜区间的位置关系**（适宜/可能适宜/部分满足/不利）；
- 哪些参数缺失导致无法判断（温度或湿度）；
- 该判断**不成立**的情形（已排除真菌、非目标病害）。

### 不能回答什么

- 病害发生概率、发病日期、病情严重度；
- 真实叶面湿润时长（系统用 RH 代理，漏报率已量化在页面 5）；
- 侵染量、初始菌源、田间孢子浓度；
- 逐日适宜度累积（系统只做一次静态判定，不做逐时累积）；
- 非南方锈病的环境适宜度（茎基腐/叶斑/穗腐全部 `not_modeled`）。

### 数据缺失时的行为

- 温度或湿度缺失 → `insufficient_data`（"数据不足，无法判断"），**不推断、不用0代替**（`risk_engine.py:452`）；
- 温度或湿度缺失**不阻断** M1/M2/M4/M5，缺失只登记在 `missing_inputs`；
- `confirmed_nonfungal` → `not_applicable`，并关闭全部杀菌剂路径。

### 当前数据缺口

M029（逐小时气温）、M030（冠层相对湿度）、**M031（叶面湿润时间 LWD）**、M032（降雨量与强度）、M033（风速风向）、M027（周边菌源与自然侵染压力）、M034（根区土壤含水量）；G001（LWD 无河南公开数据）。

### 是否已实现

**部分实现（仅 1 个病种、2 个变量、静态判定）。**

### 下一步最小行动

1. 把输入粒度从"日平均温/日平均湿"升级为"逐小时温湿 + 显式 LWD 字段（可空）"，LWD 缺失时沿用 RH 代理但**必须保留"代理"字样与漏报说明**；
2. 把 `disease_pressure` 从压力点计分项降级为"背景输入"，或补上其来源（见审计 F06）；
3. 不新增任何病种的数值适宜度模型，直到有该病种的环境参数来源（D 表中除南方锈病外均为 0 条河南灾后定量）。

---

## M4 田间病害证据

**一句话任务**：分别记录"是否观察到症状"和"是否经过专业诊断"，输出一个不依赖综合风险分数的田间证据状态。

**科学问题**：是否观察到症状？是否经过专业诊断？是否已排除真菌性病害？

### 输入字段和单位

| 字段 | 单位 | 取值 | 缺失 | 默认值 | UI 位置 |
|---|---|---|---|---|---|
| `symptom_status` | 三态 + 缺失 | none / sparse / obvious / `None` | `None` | `None`（自定义）；预设默认 `none` | `pages/2_risk.py:157` |
| `diagnosis_status` | 四态 | not_assessed / suspected / confirmed_fungal / confirmed_nonfungal | 不可为 None | `"not_assessed"` | `pages/2_risk.py:169` |
| `pre_flood_baseline` | 四态 | unknown / none / sporadic / established | 不可为 None | `"unknown"` | `pages/2_risk.py:180` |
| `disease_pressure` | 四态 | low / moderate / high / unknown | `None` | `None` | `pages/2_risk.py:208` |

### 当前计算或判断规则

`risk_engine.py:374 _field_evidence_status` —— **症状与诊断两条独立分支，先诊断后症状**：

```
diagnosis == confirmed_fungal     → 已确认真菌性病害
diagnosis == confirmed_nonfungal   → 已排除真菌性病害
symptom == obvious                 → 症状明显，尚未确诊
symptom == sparse                  → 零星异常，尚未确诊
diagnosis == suspected             → 已标记疑似，尚未确诊
symptom is None                    → 症状状态缺失
else                               → 尚未发现症状
```

配套规则：`risk_engine.py:607 _diagnosis_decision`（诊断窗口）、`risk_engine.py:471 _pressure_points`（压力点）、`risk_engine.py:491 _stage_disease_note`（生育期—病害冲突提示）。

**关键：症状状态与诊断状态互不推导，代码中没有"症状→确诊"的隐含推断。**

### 输出字段及可能取值

`field_evidence_status` ∈ 已确认真菌性病害 / 已排除真菌性病害 / 症状明显，尚未确诊 / 零星异常，尚未确诊 / 已标记疑似，尚未确诊 / 症状状态缺失 / 尚未发现症状。

### 实际代码位置和函数名

`risk_engine.py:374 _field_evidence_status`、`:390 _known_and_unknown_evidence`、`:471 _pressure_points`、`:607 _diagnosis_decision`；`ui_common.py:58–59` 标签；`case_packs/henan_maize_2026/case.json → labels.symptom / labels.diagnosis / labels.baseline`。

### 每条证据

| 证据 | 来源 | 等级 | 适用条件 | 不适用条件 |
|---|---|---|---|---|
| 诊断前置（用药前必须有诊断/高置信识别） | S12 E004 证据矩阵 | `project_assumption`（含 `official_guidance` 成分：DB41/T 2668） | 全部防治建议 | 不得由综合风险分数开药 |
| 禁止自动处方（产品名/剂量/自动处方） | S13 E010 证据矩阵 | `project_assumption`（含 `official_guidance` 成分） | 全部防治输出 | 不得输出药剂与剂量 |
| 洪涝前基线只能取田块值 | G003 缺口表 | `missing` | — | 县级/区域通报不得代替田块基线（代码 `risk_engine.py:508` 已写入文案） |
| 症状与诊断记录本身 | 用户/田块录入 | `project_assumption`（本项目**没有**自采田间观测） | — | 系统不校验来源；录入值无证据等级字段 |

### 能回答什么

- 当前田间证据处于 5 类状态的哪一类；
- 是否可以进入防治决策（仅 `confirmed_fungal` 可）；
- 哪些仍不能判断（未见症状 ≠ 未感染；疑似未确诊 ≠ 病原已知）。

### 不能回答什么

- 病害发生概率、严重度、病情指数；
- 病害的病原归属（除 confirmed_fungal / confirmed_nonfungal 两个粗分类外）；
- 首次症状日期与退水日的时滞（无输入字段）；
- 涝后病情相对洪涝前的增量（基线通常为 unknown）。

### 数据缺失时的行为

- `symptom_status is None` → "症状状态缺失"，诊断窗口 `data_insufficient`，**不得视为未见症状**（`risk_engine.py:617`）；
- `diagnosis_status == "suspected"` → 诊断窗口 `required`（先取样送检），防治窗口 `pending_diagnosis`；
- `diagnosis_status == "confirmed_nonfungal"` → 环境适宜度 `not_applicable`、防治窗口 `no_fungicide`、压力点归零 —— **单模块失效不阻断其他模块**（M1/M2/M5 仍正常输出）；
- `pre_flood_baseline == "unknown"` → 追加缺失提示，不作推断。

### 当前数据缺口

**M019（洪涝前基线与调查日期）、M020（目标病害代码与疑似病原）、M021（首次症状日期）、M022（病株率/病叶率/病情指数）、M024（诊断方法/日期/结果：镜检/PCR/分离）、M025（退水后 3/7/14 天连续调查）、M026（照片/样方 GPS/样本编号）、M023（受害组织）**；G003/G005/G006。

### 是否已实现

**已实现（状态机与门控规则完整），但底层数据全部为用户录入，项目自身无 `observed_field` 证据。**

### 下一步最小行动

1. 在字段采集模板中把"症状"与"确诊"拆成两组独立字段（现有模板已有 `symptom_status` / `diagnosis_status`，**还需补** `diagnosis_method`、`diagnosis_date`、`diagnosis_result`、`first_symptom_date`、样方固定点病情）；
2. 给用户录入的每个田间字段加 `evidence_level` 与 `source`（`data/field_observation_template_v0.6.csv` 已有 `evidence_level` 列，但田块数据管理页未强制其来源类型）；
3. 不把 `disease_pressure` 当作已量化因子（见审计 F06）。

---

## M5 干预窗口

**一句话任务**：给出排水、巡查、诊断、防治四段窗口的状态与动作，并明确指出哪些作业条件会阻止行动。

**科学问题**：何时排水、何时巡查、何时取样诊断、何时可考虑防治？哪些田间/气象/安全条件会阻止行动？

### 输入字段和单位

| 字段 | 单位 | 用途 | 缺失处理 |
|---|---|---|---|
| `standing_water` | 三态 | 排水/巡查/防治三段的硬门控 | `None` → 巡查"作业条件未知"、防治"数据不足" |
| `flood_days` / `waterlog_days` | 天 | 排水窗口状态分支 | `None` → 排水窗口 `data_insufficient` |
| `drainage_delay_hours` | 小时 | 排水窗口 open/closing/delayed 分支 | `None` → `data_insufficient` |
| `symptom_status` / `diagnosis_status` | 三态/四态 | 诊断窗口与防治窗口 | 症状缺失 → 诊断/防治 `data_insufficient` |
| `wind_speed_ms` | m/s（预计作业风速） | 防治作业安全上限 R016 = 3.3 | `None` → `data_insufficient` |
| `temperature_c` | ℃（日平均） | 防治作业安全上限 R017 = 30 | `None` → `data_insufficient` |
| `crop_stage` / `target_disease` | 枚举 | 病害策略与生育期冲突提示 | 目标病害缺失 → 防治 `data_insufficient` |

> **注意 `temperature_c` 被 M3 与 M5 共用**：在 M3 中它表示"病害环境温度（适宜度判据）"，在 M5 中它表示"施药作业温度上限"。同一个数值承担两种不同解释（审计 F05）。

### 当前计算或判断规则

| 窗口 | 函数 | 状态取值与触发条件 |
|---|---|---|
| 排水 | `risk_engine.py:514 _drainage_decision` | `standing_water is True` → `active`（立即排水）；明水渍水均 0 → `not_applicable`；任一核心天数缺失 → `data_insufficient`；`drainage_delay_hours ≤24` → `open`；`≤72` → `closing`；`>72` → `delayed` |
| 巡查 | `risk_engine.py:576 _scouting_decision` | `standing_water is True` → `blocked_safety`；`None` → `condition_unknown`；否则 `scheduled`，计划 = 排水后 3/7/14 天（R010–R012）+ 常规每 7 天（R013）+ 台风/强降雨后每 3 天（R014） |
| 诊断 | `risk_engine.py:607 _diagnosis_decision` | `confirmed_fungal` → `completed_fungal`；`confirmed_nonfungal` → `completed_nonfungal`；症状缺失 → `data_insufficient`；`symptom == none` → `standby`；其余 → `required` |
| 防治 | `risk_engine.py:634 _treatment_decision` | `confirmed_nonfungal` → `no_fungicide`；按病害 `treatment_policy` 分支（`diagnosis_only` / `harvest_monitoring` / `consult_only` / `fungal_open`）；`fungal_open` 且未确诊 → `pending_diagnosis` / `monitor` / `prepare_early`；已确诊后：`standing_water is True` → `blocked_water`；`None` → `data_insufficient`；风速 >3.3 或温度 >30 → `blocked_weather`；否则 `open`（附 R015 的 7–10 天复查） |

**限制条件输出**：`blocked_water`（积水限制）、`blocked_safety`（安全限制）、`blocked_weather`（气象限制）、`condition_unknown`（作业条件未知）、`data_insufficient`（数据不足）、`no_fungicide`（禁用杀菌剂方案）。

### 输出字段及可能取值

`windows` = 4 个 `WindowDecision(window, status, action, evidence)`；另有 `drainage_window`、`disease_window`（字符串）、`monitoring_plan`、`disease_window_precise_days`（**恒为 `"unknown"`**，`risk_engine.py:1002`）。

### 实际代码位置和函数名

`risk_engine.py:514 _drainage_decision`、`:576 _scouting_decision`、`:607 _diagnosis_decision`、`:634 _treatment_decision`、`:814 assess`；`pages/3_intervention.py:43–58`（四段窗口表）、`:60–94`（APSIM 排水时限参考）；`ui_common.py:76–100`（窗口状态中文标签）。

### 每条证据

| 证据 | 来源 | 等级 | 适用条件 | 不适用条件 |
|---|---|---|---|---|
| R005 排水 3–4 天共同临界带 | S15 E005 | `project_assumption`（多来源综合） | 排水窗口 closing/delayed 分支 | 不得换算逐日损失率；不得作普适阈值 |
| "排水越早越有利" | S01 闫振华 2023 | `public_observed` | 孕穗期、漯河 2021、及时排水 vs 延迟 3 天 | 仅孕穗期；仅该试验 |
| R010–R012 排水后 3/7/14 天巡查 | S14 E017 本项目自建流程 | `project_assumption` | 巡查日程 | **不得称经验证的发病起始日** |
| R013 常规每 7 天、R014 台风后每 3 天 | S09 E007 / DB41/T 2668 | `official_guidance` | 巡查频率 | 不得作为生物学风险窗口；不得仅因"过了 3 天"就建议施药 |
| R015 施药后 7–10 天复查 | S11 E011 | `literature_prior` + `official_guidance` | 已施药后的复查间隔 | 不得自动开具第二次施药 |
| R016 风速上限 3.3 m/s、R017 温度上限 30℃ | S10 E012 / DB41/T 2668 | `official_guidance` | 施药作业可行性 | 风速/温度不是病害风险指标；不得在积水或机械不安全时推荐施药 |
| R018 诊断前置、R019 禁止自动处方 | S12 / S13 | `project_assumption` | 全部防治路径 | 不得由综合风险分数开药 |
| APSIM 排水时限参考（28.5%/28.8%、47.0%/45.8%） | S17 | `simulated_validation` | APSIM 官方验证情景 | **不自动替换田块输入；不计算河南本地损失**（页面已声明） |

### 能回答什么

- 现在该做什么、按什么顺序做（排水 → 巡查 → 诊断 → 防治）；
- 哪些条件正在阻止行动（积水 / 风速 / 高温 / 未确诊 / 无安全作业条件）；
- 每条建议的依据编号与等级可在页面 5 追溯。

### 不能回答什么

- 具体的"第 N 天必须施药"（`disease_window_precise_days` 恒为 unknown）；
- 药剂名称、剂量、开处方；
- 成本收益、亩成本、投入产出比（G005，无公开排涝亩成本）；
- 病害概率或未来产量。

### 数据缺失时的行为

- 每个窗口**独立**判断，缺一个字段只让**对应**窗口变成 `data_insufficient`，其余窗口照常输出（`ui_common.py:364` 明确提示"缺失值未被当作 0 或安全条件"）；
- `standing_water is None` → 巡查 `condition_unknown`、防治 `data_insufficient`，但排水窗口仍可由天数给出；
- 已排除真菌 → 防治窗口 `no_fungicide`，**其余三个窗口不受影响**。

### 当前数据缺口

M035（实际排水方式与作业时间）、M036（农药产品/剂量/施药时间）、M037（追肥/中耕/扶正）、M038（排水与施药成本）、M033（田块风速与风向）、M029（逐小时气温）；G005。

### 是否已实现

**已实现（4 段窗口 + 限制条件 + 证据编号追溯），但支撑数值全部是公开文献/标准先验，没有本地实测校准。**

### 下一步最小行动

1. 把 `temperature_c` 拆成 `env_temperature_c`（病害环境）与 `operation_temperature_c`（作业温度），消除一处双解释；
2. `pages/3_intervention.py:87–91` 的 APSIM 百分比是**硬编码文本**，改为从 `data/simulation/lizaso_maize_1991_summary.csv` 读取（当前数值与 CSV 一致，但属易失效的复制粘贴，见审计 F09）；
3. 在巡查窗口的 `action` 里补一句"该计划与暴露数据无关，仅为巡查节奏"。

---

## 附：五模块"当前各自能做到什么"速查

| 模块 | 能做 | 不能做 | 可审计证据 | 状态 |
|---|---|---|---|---|
| M1 洪涝暴露 | 天数→关注分级、缺失不填 0、状态文字 | 水深、时间序列、区域分级 | 有（E04/C004，公开文献先验） | 部分实现 |
| M2 作物胁迫与产量 | 关注分级 + 限定性产量锚点文字 | 减产率预测、品种效应 | 有（E04/C004，公开文献先验） | 部分实现 |
| M3 病害环境适宜性 | 静态温湿区间判定 + 缺失即"数据不足" | 病害概率、LWD、累积适宜度、逐时判定 | 有（DB41/T 2668、国家指导意见，官方规范） | 部分实现（1 病种 2 变量） |
| M4 田间病害证据 | 5 态证据状态、诊断门控、症状/诊断独立 | 严重度、病原细分、时滞 | 无自采；规则为项目假设 | 规则已实现，数据缺失 |
| M5 干预窗口 | 4 段窗口 + 作业限制 | 精确施药日、处方、成本 | 有（E007/E012/E017，官方规范 + 项目流程） | 已实现，未校准 |
