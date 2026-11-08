# v0.4 逻辑测试情景

文件：`data/demo_scenarios_v0.4.csv`

这些记录是软件逻辑测试，不是田间观测，不是农业实测数据，也不能用于模型准确率或效果评价。

所有记录的 `evidence_level` 均为 `TEST_ONLY`，`notes` 均明确写明“合成逻辑测试，不是田间观测”。

## 预期结果

| 记录 | 测试目的 | 数据完整性 | 处置优先级 | 环境适宜度 | 防治窗口 |
|---|---|---|---|---|---|
| TEST-001 | 短时淹水 | complete | 中 | partial | monitor |
| TEST-002 | V6严重淹水 | partial | 中—高 | optimal | prepare_early |
| TEST-003 | 仅长时渍水 | partial | 高—很高 | optimal | pending_diagnosis |
| TEST-004 | R3确认真菌病害 | complete | 高—很高 | optimal | open |
| TEST-005 | 已排除真菌病害 | partial | 中 | not_applicable | no_fungicide |
| TEST-006 | 环境数据缺失 | partial | 中 | insufficient_data | monitor |
| TEST-007 | 核心暴露缺失 | insufficient_core | 数据不足 | insufficient_data | monitor |
| TEST-008 | 自定义全空 | insufficient_core | 数据不足 | not_modeled | data_insufficient |

## 使用方式

1. 打开网页的“v0.4 田块记录 CSV 导入与导出”区域；
2. 上传 `demo_scenarios_v0.4.csv`；
3. 应得到8条有效记录、0个校验错误；
4. 下载结果CSV，只用于检查软件逻辑。

若页面结果与本表不一致，应视为代码或字段映射回归，不能解释为农业规律变化。
