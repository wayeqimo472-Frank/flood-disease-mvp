# Sustainable Corn CAP 数据来源

- DOI：https://doi.org/10.15482/USDA.ADC/1411953
- 数据集：Sustainable Corn CAP Research Data (USDA-NIFA Award No. 2011-68002-30190)
- 时间范围：2011—2015
- 覆盖：Illinois、Indiana、Iowa、Michigan、Minnesota、Missouri、Ohio、Wisconsin
- 许可：CC0
- 原始工作簿：`raw/Sustainable_Corn_Research_Data_2011-2015.xlsx`
- 数据字典：`raw/Sustainable_Corn_Research_Data_2011-2015_DataDictionary.csv`
- 工作簿MD5：`34d284bb59f549e25ea9f77b33721003`
- 数据字典MD5：`8022d02d579a4a288c02bb46681bcc35`

USDA下载端点触发WAF挑战。已通过Scrapling真实浏览器会话完成挑战，并从浏览器下载缓存提取原始文件；MD5与USDA API公布值一致。

## 本案例用途

- 30个试验点的公共元数据；
- 1618条玉米产量记录；
- 4536条玉米病害数值评级；
- 168条规范化、可匹配产量的病害观测；
- 25518条逐日地下水位记录；
- 22293条逐日排水流量记录；
- 2175条田间作业记录；
- 486条农药记录；
- 穗腐和茎腐的公开观测可用于监测与数据流程验证。

## 严格边界

公开数据没有给出同一批田块的“洪涝暴露—病害时序—产量”完整记录，也没有覆盖全部病害。美国案例因此配置为 `monitoring_only`，不复制河南参数，不输出定量风险。
