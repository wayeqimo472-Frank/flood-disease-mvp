# 洪涝次生灾害风险原型

当前完成参数先验、最小风险计算核心、可切换案例包、本地 SQLite 持久化、公开数据拼接和 Streamlit 六页原型。

当前案例包：

- `henan_maize_2026`：唯一完成本地定量规则封装的默认案例；
- `us_corn_belt_cscap_2011_2015`：美国玉米带CC0公开观测案例，只提供监测框架，不输出本地定量风险。

## 当前文件

- `data/model_parameter_priors_v0.2.csv`、`data/decision_rules_v0.3.csv`、`data/gap_availability_v0.1.csv`：v0.5历史输入，保留用于审计。
- `case_packs/henan_maize_2026/case.json`：河南夏玉米案例的元数据、标签、品种、病害和预设。
- `case_packs/henan_maize_2026/`：案例包独占的参数、规则和缺口表。
- `case_packs/us_corn_belt_cscap_2011_2015/`：美国玉米带公开数据、处理结果和监测案例。
- `case_pack.py`：案例包发现、读取和路径校验。
- `storage.py`：本地 SQLite 观测批次、田块记录和计算历史。
- `data_integration.py`：公开数据导入、ICASA 映射、GeoJSON 与 SAR 指标校验。
- `data/icasa_field_mapping_v0.1.csv`：本项目字段与 ICASA 标准变量子集的映射。
- `tools/import_public_data.py`：把美国 CSCAP、公开证据和缺口表写入 `app.db`。
- `data/public_dataset_register_v0.2.csv`：公开数据来源、许可、字段边界和本地状态。
- `data/public_data_gap_matrix_v0.2.csv`：项目级P0—P2数据缺口矩阵。
- `data/all_missing_data_v0.3.csv`：50项逐字段缺失数据总表。
- `data/public_evidence_v0.2/`：One Acre Fund、受淹玉米试验、DIVINE和意大利LWD的整理结果。
- `tools/build_public_evidence_v0_2.py`：公开证据文件重建脚本。
- `docs/source_selection_v0.2.md`：来源取舍和证据边界。
- `docs/ae_integration_v0.3.md`：A—E专项调研的选择性整合说明。
- `risk_engine.py`：规则型风险与干预窗口计算核心。
- `app.py`：Streamlit 导航入口。
- `ui_common.py`：共享标签、情景状态、结果卡片和安全提示。
- `pages/`：项目总览、风险筛查、干预窗口、田块数据、科研依据、数据拼接六个页面。
- `batch_io.py`：田块观测CSV模板、校验、批量计算和结果导出。
- `tests/test_risk_engine.py`：典型情景自检。
- `tests/test_app.py`：页面冒烟测试。
- `tests/test_batch_io.py`：CSV导入与逐行校验测试。
- `tests/test_case_pack.py`：案例包发现、元数据和作用域测试。
- `tests/test_storage.py`：SQLite导入、去重、计算历史和备份测试。
- `data/field_observation_template_v0.6.csv`：带案例、地区和统一单位字段的空白田块观测模板。
- `data/demo_scenarios_v0.4.csv`：明确标注为逻辑测试的合成情景。
- `data/supplementary_source_assessment_v0.1.csv`：补充资料逐项可用性判断。
- `data/public_evidence_catalog_v0.1.csv`：公开数据集来源、许可证、用途和限制。
- `data/public_flood_case_maize_v0.1.csv`：真实淹水田与未淹对照的NDVI时序摘要。
- `data/public_waterlogging_survival_maize_v0.1.csv`：80个玉米基因型的9天涝渍存活率。
- `data/public_disease_progress_maize_v0.1.csv`：两季玉米病害时间进展模型参数。
- `data/public_evidence_v0.1.sqlite`：页面实际读取的只读公开证据数据库。
- `public_evidence_db.py`：只读证据库访问接口。
- `scripts/build_public_evidence_db.py`：从公开证据CSV重建SQLite数据库。
- `docs/v0.4_acceptance_freeze.md`：v0.4验收、哈希和冻结边界。
- `docs/v0.6_case_pack_and_sqlite.md`：案例包、SQLite结构和单用户边界。
- `docs/v0.7_data_integration.md`：ICASA、FTW、SAR 和公开数据的拼接边界。
- `docs/public_data_expansion_v0.2.md`：2026-11-13公开数据扩展和缺口判断。
- `docs/all_missing_data_v0.3.md`：全部缺失字段的分组说明和优先级。
- `docs/demo_scenarios_v0.4.md`：逻辑测试情景及预期结果。
- `docs/field_data_request_packet_v0.4.md`：合作方数据请求说明。

## 运行

```powershell
.\.venv\Scripts\python.exe risk_engine.py
.\.venv\Scripts\python.exe tools\import_public_data.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\streamlit.exe run app.py --server.address 127.0.0.1
```

## 当前输出

- 明确区分默认预设在载入时的“情景假设值”和用户已提交输入；
- 显示数据完整性、缺失字段，以及空值不按0处理的限制；
- 涝渍暴露事实与“已定量/未分级”状态；
- 区域淹水分级；
- 南方锈病环境适宜度；
- 田间症状与诊断证据状态；
- 综合“处置优先级”，并明确它不是病害发生概率；
- 当前可判断和因基线、LWD、诊断缺失而不能判断的内容；
- 症状观察与专业诊断保持独立；排除真菌后关闭杀菌剂防治路径；
- 品种只按已知身份做文字说明，不用无证据的“品种抗性”调整风险；
- 排水、巡查、诊断、病害防治四段窗口；
- 诊断前置和气象/积水作业限制；
- 洪涝前病情基线、主导品种和缺口数据说明；
- 按实际执行路径展示参数用途、使用字段、时间阈值、数值区间和限制说明。
- 下载空白田块观测模板，上传CSV进行逐行校验和批量计算，并导出结果。
- 五个页面通过侧边栏导航，当前评估状态始终可见；
- CSV上传在当前浏览器会话中保留，并写入 `data/app.db`；相同文件按 SHA256 去重；
- 田块数据页可重新载入数据库中的历史批次，并下载原始文件和计算结果；
- 总览页显示最近计算历史，计算结果与案例包版本可追溯。
- 数据拼接页展示美国 CSCAP、公开案例、ICASA 字段映射、田块 GeoJSON 和 SAR 地块指标接口。

## 案例包与数据库

默认案例包为：

```text
henan_maize_2026
```

页面侧边栏可以直接切换案例包。也可通过环境变量指定启动时默认案例：

```powershell
$env:FLOOD_APP_CASE_ID="henan_maize_2026"
```

切换到美国监测案例：

```powershell
$env:FLOOD_APP_CASE_ID="us_corn_belt_cscap_2011_2015"
```

美国案例的 `risk_model` 为 `monitoring_only`，页面会明确显示“仅监测（无本地定量校准）”，不会借用河南参数生成风险分级。

数据库默认位置：

```text
D:\360MoveData\Users\Lenovo\Desktop\大创项目\flood_disease_mvp\data\app.db
```

如需把数据库放到其他 D 盘目录，可在启动前设置：

```powershell
$env:FLOOD_APP_DB_PATH="D:\APP\flood_disease\app.db"
```

数据库包含：

- `import_batches`：CSV文件、哈希、导入时间和错误摘要；
- `field_observations`：逐田块原始字段与计算结果；
- `assessment_runs`：单次风险计算的输入、案例版本和结果。
- `external_datasets`、`external_records`：公开数据的来源、许可、哈希和逐行记录。
- `plot_geometries`：FTW 预测或现场测绘的地块几何。
- `plot_flood_metrics`：遥感推算的地块淹没比例、洪水起止和退水日。

当前数据库已预载一个美国案例外部观测批次：168条，案例ID为 `us_corn_belt_cscap_2011_2015`。计算历史为空。

美国案例数据由 [tools/build_us_cscap_case.py](tools/build_us_cscap_case.py) 从USDA原始工作簿重建。原始工作簿MD5已核验，处理结果包含：

- 30个试验点；
- 1618条玉米产量记录；
- 4536条玉米病害数值评级；
- 168条规范化病害观测；
- 25518条逐日地下水位；
- 22293条逐日排水流量；
- 2175条田间作业记录；
- 8个州的站点元数据。

## 当前限制

- 处置优先级是管理关注分类，不是病害发生概率；
- 少于5天的渍水表示“存在胁迫但未达到定量锚点”，不标为低风险；
- E04只用于生育期×淹水历时的粗略关注分级；
- E14的3/5/7天需要独立的区域遥感像元数据；当前没有该输入，不用田块明水天数替代；
- E02 的精确早晚期施药天数仍未知；
- E20 不能提供可靠的严重度—产量斜率；
- 南方锈病以外的病害暂不输出数值风险；
- 不建立“洪涝后第 N 天”风险曲线；
- 不自动提供农药名称、剂量或处方；
- 区域或推算值不会替代田块级缺失数据；
- 当前为单用户本地数据库，没有登录、多用户权限或并发协作；
- SQLite数据库没有自动备份，重要数据需要定期复制 `app.db`；
- 田块数据页提供“创建本地数据库备份”按钮，备份写入 `data/backups/`；
- 当前仍不接云数据库；需要多人协作时再迁移 PostgreSQL；
- 核心涝渍暴露缺失时处置优先级显示“数据不足”，但环境等可判断维度仍独立输出；
- 温度或湿度缺失时，南方锈病环境适宜度显示“数据不足”；
- 当前不输出病害导致的精确产量损失；
- 所有结果都必须保留“文献先验/情景规则”标签。
- 美国案例不输出定量风险，原因是公开数据没有形成同一田块的洪涝—病害连续时序。
- FTW 和 SAR 当前以独立数据接口接入，不把大型模型、遥感瓦片或 PyTorch 依赖打包进 Streamlit。
- 遥感边界和淹没比例统一标记为 `remote_sensed`，不能替代现场水深、实际退水时间或田间病情。
