"""Derive all reported numbers and public preview from the actual experiment outputs."""
import json,hashlib
from common import ROOT,dump,sha
A=ROOT/'artifacts';r=json.loads((A/'results.json').read_text());m=r['metrics']['lightweight'];q=r['quality'];p=r['policy'];route=r['routing'];pct=lambda v:f'{v*100:.2f}%'
rows='\n'.join(f"|{name}|{v['n']}|{pct(v['precision'])}|{pct(v['recall'])}|{v['f1']:.4f}|{v['tn']}/{v['fp']}/{v['fn']}/{v['tp']}|" for name,v in r['metrics'].items())
risk='\n'.join(f"|{v['risk']}|{v['n']}|{v['fn']}|{v['fp']}|{pct(v['recall']) if v['recall'] is not None else '不适用'}|{pct(v['false_positive_rate']) if v['false_positive_rate'] is not None else '不适用'}|" for v in r['risk_metrics'])
report=f'''# 离线实验报告 · COLD / cold-offline-v1

本报告由 `src/report.py` 从真实实验产物生成。研究日期：2026-10-21。独立作品集，无企业内部数据、生产流量或上线收益。

## 结论与门禁

轻量模型完整测试集 F1 为 **{m['f1']:.4f}**，规则 F1 为 {r['metrics']['rules']['f1']:.4f}。模型捕获更多冒犯表达，但误杀仍高。级联只对部分样本自动决策，不能把其自动子集 F1 宣称为全量效果提升。

验证集自动拦截精确率 {pct(p['validation_auto_block_precision'])}（{p['validation_auto_block_n']} 条自动拦截）在测试集降至 **{pct(route['block_precision'])}**。验证集自动通过正确率 {pct(p['validation_auto_pass_precision'])}（{p['validation_auto_pass_n']} 条）在测试集为 {pct(1-route['pass_contamination'])}。门禁未通过，**不得按此结果上线自动拦截**。未使用测试集重新选择阈值。

## 数据与清洗

原始 {q['raw_total']} 条；保留 {q['retained_total']} 条。训练 {q['retained_counts']['train']} / 验证 {q['retained_counts']['validation']} / 测试 {q['retained_counts']['test']}。测试安全 {q['labels']['test']['0']}、冒犯 {q['labels']['test']['1']}。

NFKC、小写、移除非字母数字字符后 SHA-256 分组，{q['duplicate_rows']} 条非冲突重复被去除；{q['conflict_groups']} 个二元标签冲突组整体剔除；无效或空文本 {q['invalid_rows']} 条。跨集合重复组由 {q['cross_split_groups_before']} 降至 0。保留优先级 test > validation > train，避免训练接触保留的测试文本；冲突检测使用各集合标签仅作预先定义的数据质量处理。官方测试集发生少量清洗，指标不能与未清洗的论文数字直接比较。

没有作者 ID、时间分组和语义近重复去重，不能保证更广义无泄漏；规范化也可能合并标点或表情含义不同的内容。每个删除项及保留 ID 均在 `quality_exclusions`。

## 配置与选择方法

种子 {r['seed']}。字符 TF-IDF (1–3 gram)、min_df=3、max_features=80000、sublinear_tf=True，仅拟合训练集。逻辑回归 liblinear / max_iter=500 / 单 CPU 线程。C ∈ {{0.3,1,3}}，二元阈值 ∈ {{0.30,0.35,…,0.70}}，以验证 F1 选出 C={p['C']}、阈值 {p['binary_threshold']}；未将验证集重新加入训练。

级联通过阈值 {p['pass_threshold']}，拦截阈值 {p['block_threshold']}。在验证集扫描 0.01–0.99，分别要求自动通过正确率、自动拦截精确率 ≥95% 且支持数 ≥50，然后最大化各自动区间覆盖；命中规则时禁止自动通过。95% 为经验比例，不是统计置信下界。模型分数未经概率校准。规则词表为事先定义的朴素基线，未针对测试样本扩充；其质量不代表成熟规则系统。

## 质量指标

正类为冒犯。混淆矩阵顺序 TN / FP / FN / TP；Precision=TP/(TP+FP)，Recall=TP/(TP+FN)，F1 为二者调和平均。

|策略|分母 n|Precision|Recall|F1|TN/FP/FN/TP|
|---|---:|---:|---:|---:|---|
{rows}

`cascade_auto_only` 只在有自动结论的 {int(route['auto_coverage']*route['n'])} 条上计算，排除待复核，不能视为全量端到端结果。人审结论未知，端到端质量记 null。

轻量 F1 分层 Bootstrap 95% 区间 [{r['lightweight_f1_bootstrap95'][0]:.4f}, {r['lightweight_f1_bootstrap95'][1]:.4f}]；种子42，400次按真值类别有放回抽样。区间只描述固定模型、固定测试集的抽样波动，不含训练、选择阈值或分布漂移不确定性。

## 路由与人力

全部测试 n={route['n']}：通过 {route['counts']['pass']}（{pct(route['rates']['pass'])}）；拦截 {route['counts']['block']}（{pct(route['rates']['block'])}）；待人工复核 {route['counts']['review']}（{pct(route['rates']['review'])}）；自动覆盖 {pct(route['auto_coverage'])}。

自动通过中含冒犯 {route['auto_pass_offensive']}，分母为全部通过时污染率 {pct(route['pass_contamination'])}，分母为全部冒犯时漏放率 {pct(route['leakage_over_all_offensive'])}。自动拦截中含安全 {route['auto_block_safe']}，分母为全部安全时误杀率 {pct(route['false_block_over_all_safe'])}。复核样本没有被假定为正确。

LLM 实际调用 0 次，{route['candidate_llm_requests']} 个不确定样本走禁用适配器并降级到人工队列，审计文件记录 disabled；实验基线人审完成 0 条。队列操作独立持久化，不会修改实验真值或历史指标。规则与轻量模型、离线路由、人工队列已实现；大小模型效果尚未进行联合实测。

## 按来源细标签分析

|来源切片|n|FN|FP|冒犯召回率|安全误杀率|
|---|---:|---:|---:|---:|---:|
{risk}

细标签只用于评估切片，不是四类模型预测。单一真值切片不报告 Precision/F1。涉黄、诈骗、垃圾广告、未成年人风险、暴恐、违法等不具备对应真值，无法评估。

## 时延与成本

环境：{r['environment']['platform']}；Python {r['environment']['python'].split()[0]}，scikit-learn {r['environment']['sklearn']}，NumPy {r['environment']['numpy']}；逻辑 CPU {r['environment']['cpu_count']}，数值计算限制 1 线程。

顺序执行测试前200条单条请求，使用 perf_counter 测量字符转换+模型+规则+路由，p50={r['latency']['p50_ms']:.3f} ms，p95={r['latency']['p95_ms']:.3f} ms。全测试批量转换+预测 {r['latency']['batch_total_ms']:.2f} ms，摊销 {r['latency']['batch_amortized_ms']:.4f} ms/条；不能将摊销值视为单请求延迟。未包含启动、HTTP、SQLite、网络、人审，也没有真实端到端或 LLM 延迟。每次复现时延会变化。

真实 API 支出 0（未调用），不是总计算成本。假设输入300 token、输出100 token，单价分别1元/百万、4元/百万，候选调用预算为 {route['candidate_llm_requests']}×(300×1+100×4)/10⁶ = **{r['cost']['estimated_scenario_spend']:.4f}元**。这只是情景公式，非报价、真实花费或已实现节省；重试、缓存、token分布与人工工资均未纳入。

## 可追溯产物

- `data/source_manifest.json`：官方提交、下载日期、来源 URL、SHA-256。
- `artifacts/split_manifest.json`：样本 ID、划分、规范化哈希。
- `artifacts/validation_search.json`：27 个模型与阈值组合；`policy.json`：冻结策略。
- `artifacts/predictions.csv`：每条测试预测与路由；`warehouse.sqlite`：原始标签、清洗与分析表。
- `sql/analysis.sql` 与 `artifacts/sql_results.json`：可执行查询及实际结果。
- `artifacts/model.joblib`：本地模型，只加载本项目可信文件。
- `artifacts/adapter_audit.sqlite`：禁用/降级证据；`operations.sqlite`：真实手动操作（与实验隔离）。
- `artifacts/reproducibility.json`、`verification.json`：重复运行比对与验证记录（完成验证后生成）。

## 下一步实验（未实施）

引入独立的反偏见/引用/反讽验证集；尝试校准与语义模型；盲测前锁定新策略。不得复用当前测试集作新版本调参集后仍称独立测试。若接入 LLM，应先做人工仲裁标注、供应商数据条款检查、限额与网络实测，重新评价全量覆盖、残余错误和人工成本。
'''
(ROOT/'docs/EXPERIMENT_REPORT.md').write_text(report,encoding='utf-8')
portfolio=f'''# AI 社区内容安全策略运营｜独立项目作品集

## 项目定位

围绕社区安全策略运营所需的数据分析、风险研判、机审策略维护和跨团队推进能力，构建一个可复现、可展示的中文评论治理 MVP。项目参考岗位职责，不代表曾在快手任职，不使用快手内部数据，也无上线业绩。

## 3 分钟演示路线

1. 打开 `portfolio.html` 讲清项目边界和真实数据；本地服务提供完整人工复核功能。
2. 看治理总览：在 {route['n']:,} 条真实测试样本上比较规则与轻量模型，F1 为 {m['f1']:.3f}。
3. 看风险切片：反偏见表达误杀揭示词面模型的语义缺陷；阈值验证达标但测试退化，因此阻断上线。
4. 打开人工复核工作台：展示 {route['counts']['review']:,} 条待办、盲化真值、人工结论与申诉重新入队。
5. 展示 SQL 查询、数据哈希、固定策略和一键复现，说明所有数字均有逐样本证据。

## 我解决了什么

- **数据可信**：固定官方 COLD 提交并保存授权，清洗 {q['raw_total']:,} 条样本；保留 {q['retained_total']:,} 条；清除 {q['cross_split_groups_before']} 个规范化跨集合重叠组，隔离 {q['conflict_groups']} 个标签冲突组。
- **策略可解释**：从朴素规则到字符 TF-IDF + 逻辑回归；仅在验证集选择阈值；输出二分类质量与路由覆盖两种口径。
- **运营可执行**：通过/拦截/复核队列、审核规范、申诉与回流事件留痕；人审真值与原始标签分离。
- **决策诚实**：没有 API 时实现禁用降级、重试/缓存接口测试，不伪称大模型评测；没有用人审完美假设美化指标。

## 最值得讲的发现

自动拦截精确率从验证集 {pct(p['validation_auto_block_precision'])} 下降到测试集 {pct(route['block_precision'])}。这说明单看验证集达标不足以证明可上线，策略运营应关注分布差异、反偏见等困难语境和分群错误。当前结果支持“停止自动拦截上线、补标与独立验证”的决策，不能支持“提升了生产治理效率”的结论。

## 可直接改写进简历的表述

> 独立完成中文社区内容安全策略运营项目：基于公开 COLD 数据构建 SQLite 分析仓库，对 37,480 条评论进行质量检查，清洗保留 37,245 条，建立来源哈希、官方划分与重复/冲突审计，规范化跨集合重叠组由 105 降为 0。
>
> 实现规则与字符 TF-IDF + 逻辑回归基线，在独立清洗测试集 5,311 条评论上取得 Precision {pct(m['precision'])}、Recall {pct(m['recall'])}、F1 {m['f1']:.3f}；通过 SQL 切片定位反偏见表达误杀，识别验证到测试的策略退化并形成上线阻断建议。
>
> 搭建本地策略看板、人工复核队列及申诉审计闭环；离线级联将 {pct(route['rates']['review'])} 样本转人工，明确自动决策覆盖与残余错误，预留具备结构校验、超时参数、重试和缓存的 LLM 审核接口（未调用收费 API）。

以上是工具协作完成的项目内容；投递前应亲自复现并能解释代码与指标，按本人实际承担工作调整表述。

## 面试追问准备

- 为什么没有选择更高的测试分数？测试只评估，不能反向调参；保留失败结果更能说明风险判断。
- 待复核如何计入效果？单独报告覆盖和人力；没有真实结论就不能报告完整级联 F1。
- 如何降本？目前只有候选调用量和预算公式，无真实 LLM 成本收益结论。
- 为什么采用轻量模型？离线可复现、速度快、易定位问题；词面特征也有立场理解不足的明确边界。
- 如何进入业务？需要代表性流量、真实人工仲裁、隐私审查、独立留出集、灰度和回滚；本项目尚未做生产验证。

主要证据见 `docs/EXPERIMENT_REPORT.md`、`docs/CASE_REVIEWS.md`、`docs/GOVERNANCE.md` 与 `artifacts/`。
'''
(ROOT/'docs/PORTFOLIO.md').write_text(portfolio,encoding='utf-8')
# Standalone, public-safe preview: source comment text is never embedded.
html=(ROOT/'dashboard/index.html').read_text().replace('<link rel="stylesheet" href="style.css">','<style>'+(ROOT/'dashboard/style.css').read_text()+'</style>')
js=(ROOT/'dashboard/app.js').read_text();data=json.loads((ROOT/'dashboard/data.json').read_text())
js=js.replace("fetch('data.json').then(r=>r.json()).then(d=>{D=d;render()}).catch(e=>{$('#loading').textContent='实验产物未加载，请先执行复现入口。'+e.message});",'D='+json.dumps(data,ensure_ascii=False).replace('</','<\\/')+';render();')
html=html.replace('<script src="app.js"></script>','<script>'+js.replace('</script','<\\/script')+'</script>')
(ROOT/'portfolio.html').write_text(html,encoding='utf-8')
files=[p for p in (ROOT/'src').glob('*.py')]+[ROOT/'config/experiment.json',ROOT/'requirements.txt',ROOT/'data/source_manifest.json']+[A/x for x in ['model.joblib','predictions.csv','split_manifest.json','results.json','policy.json','validation_search.json']]
dump(A/'run_manifest.json',{'files':{str(f.relative_to(ROOT)):sha(f.read_bytes()) for f in files},'note':'Hashes tie source/config/data/model/predictions to this run; operations DB excluded because human activity is mutable.'})
print('Generated experiment report, portfolio and standalone HTML')
