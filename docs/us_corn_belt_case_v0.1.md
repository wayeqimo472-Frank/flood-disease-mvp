# 美国玉米带第二案例 v0.1

日期：2026-11-13

## 选择理由

Sustainable Corn CAP公开数据覆盖美国中西部8个州、30个试验点，包含：

- 玉米产量和农艺性状；
- 土壤水分、地下水位和排水数据；
- 病害虫害调查；
- 逐小时或亚小时气象接口；
- 试验设计和站点坐标。

数据许可为CC0，适合进入可追溯的案例包和数据目录。

## 实际可用数据

处理后的数据包括：

| 数据 | 数量 |
|---|---:|
| 试验点 | 30 |
| 州 | 8 |
| 玉米产量记录 | 1618 |
| 数值病害评级 | 4536 |
| 可匹配产量的规范化病害观测 | 168 |
| 逐日地下水位 | 25518 |
| 逐日排水流量 | 22293 |
| 田间作业记录 | 2175 |
| 农药记录 | 486 |

数值病害规范化后主要为：

- 穗腐病；
- 茎腐或茎基腐。

## 为什么只做监测

公开数据没有提供同一批田块的以下完整序列：

- 明水或渍水开始时间；
- 实际退水时间；
- 洪涝前病情；
- 涝后连续病情；
- 最终产量。

水表数据只覆盖少数站点，病害产量匹配又集中在另外几家站点，不能把不同田块的数据拼成因果序列。

因此美国案例配置为：

```json
"risk_model": "monitoring_only"
```

该模式允许：

- 展示真实外部观测；
- 保存区域、作物、病害和产量数据；
- 运行排水、巡查和诊断流程；
- 验证多案例包切换。

该模式禁止：

- 复制河南定量阈值；
- 输出病害概率；
- 输出精确产量损失；
- 自动推荐农药或剂量。

## 可复现文件

- 原始工作簿：`case_packs/us_corn_belt_cscap_2011_2015/raw/`
- 数据处理：`tools/build_us_cscap_case.py`
- 站点元数据：`processed/site_metadata.csv`
- 玉米产量：`processed/corn_yield.csv`
- 病害评级：`processed/disease_ratings.csv`
- 病害产量匹配：`processed/disease_yield_matched.csv`
- 地下水位：`processed/water_table_daily.csv`
- 排水流量：`processed/tile_flow_daily.csv`
- 田间作业：`processed/field_operations.csv`
- 农药记录：`processed/pesticides.csv`
- v0.6观测模板：`processed/observations_v0.6.csv`
- 校验摘要：`processed/validation_summary.json`
