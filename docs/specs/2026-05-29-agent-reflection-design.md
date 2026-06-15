# Agent 反思机制设计

> Agent 自主推理时，工具可能失败，答案可能不完整。两层反思机制让 Agent 具备自我纠错能力。

## 背景

当前 Agent（`rag/agent.py`）使用 LangChain Agent + ReAct 循环，4 个工具（retrieve/calculate/sql_query/plot_chart）。问题：

1. **工具失败无容错** — 工具抛异常或返回空，Agent 直接拿到错误信息，无法自动换策略
2. **答案无自检** — Agent 返回答案后不检查是否覆盖问题要点，可能答非所问

## 设计目标

- 工具失败时自动重试/换策略，不中断推理
- 答案出来后 LLM 自检，不达标就带反馈重跑
- 最多 2 轮反思（总共 3 次推理机会），平衡质量和成本

## 第 1 层：工具级反思

**时机：** 工具返回错误或空结果时

**策略：**

| 场景 | 处理 |
|------|------|
| 工具抛异常 | 换一种方式重试（如 calculate 报错 → 尝试 sql_query） |
| 工具返回空/"无结果" | 改写查询词重试（如 retrieve 空 → 用同义词/简化词重试） |
| 每个工具最多重试 1 次 | 不无限循环，重试 1 次仍失败则把错误信息传给 Agent |

**实现方式：** 包装工具的 `func`，在 wrapper 中捕获异常/空结果，自动触发重试逻辑。包装后的工具对 Agent 透明，不改变 LangChain Agent 接口。

```python
def _wrap_tool_with_reflection(tool: Tool) -> Tool:
    """包装工具，失败时自动重试。"""
    original_func = tool.func

    def reflective_func(inp: str) -> str:
        result = original_func(inp)
        # 如果返回空或错误，尝试重试
        if _is_empty_or_error(result):
            result = _retry_with_fallback(tool.name, inp, original_func, result)
        return result

    tool.func = reflective_func
    return tool
```

**重试策略：**
- `retrieve` 返回空 → 简化查询词（去掉修饰词）重试
- `calculate` 报错 → 尝试 `sql_query`（可能是数据查询而非计算）
- `sql_query` 报错 → 简化 SQL 重试
- `plot_chart` 报错 → 返回错误信息（图表格式问题需用户修正）

## 第 2 层：答案级自检

**时机：** Agent 返回最终答案后

**策略：**
- 用 LLM 对比「问题」和「答案」，输出结构化判断：
  - `verdict`: pass / fail
  - `missing`: 缺失的要点列表（仅 fail 时）
- fail → 将 missing 反馈给 Agent，重新推理
- 最多 2 轮自检（总共 3 次推理机会）

**自检 Prompt：**

```
你是一个答案质量审查员。请判断以下答案是否完整回答了用户的问题。

问题：{question}
答案：{answer}

判断标准：
1. 答案是否直接回应了问题的核心诉求
2. 是否遗漏了问题中的关键信息点
3. 是否包含无关或错误的信息

请用 JSON 格式回复：
{{"verdict": "pass 或 fail", "missing": ["缺失的要点1", ...]}}
```

**重跑 Prompt（自检失败时）：**

```
你之前的回答不完整，缺少以下要点：
{missing}

请重新回答原始问题，确保覆盖以上所有要点。
```

## 实现方案

**修改文件：** `rag/agent.py`

**新增函数：**
- `_wrap_tool_with_reflection(tool)` — 包装单个工具，加入重试逻辑
- `_is_empty_or_error(result)` — 判断工具结果是否为空/错误
- `_retry_with_fallback(tool_name, inp, original_func, original_result)` — 重试策略
- `_check_answer_quality(question, answer)` — LLM 自检
- `RAGAgent.run()` — 修改，加入自检循环

**不新建模块**，所有逻辑在 `rag/agent.py` 内完成。

## 调用流程

```
RAGAgent.run(question):
    tools = [_wrap_tool_with_reflection(t) for t in self.tools]
    for round in range(max_reflection_rounds + 1):  # 0, 1, 2
        answer = self._invoke_agent(question if round == 0 else feedback_prompt)
        check = _check_answer_quality(question, answer)
        if check["verdict"] == "pass":
            return answer
        # 构造反馈 prompt 继续下一轮
        feedback_prompt = f"你之前的回答不完整，缺少：{check['missing']}。请重新回答。"
    return answer  # 超过轮次返回最后一次答案
```

## 测试策略

| 测试 | 验证内容 |
|------|---------|
| 工具异常自动重试 | mock 工具第 1 次抛异常，第 2 次成功 → 最终返回正确结果 |
| 工具空结果重试 | mock retrieve 返回空 → 自动简化查询词重试 |
| 自检通过 | mock LLM 自检返回 pass → 不重跑 |
| 自检失败重跑 | mock LLM 自检返回 fail → 触发重跑 |
| 最大轮次限制 | 连续自检 fail → 最多 2 轮后返回最后答案 |
| 包装不影响正常工具 | 正常调用不触发重试逻辑 |

## 面试话术

"Agent 自主推理时，工具可能失败，答案可能不完整。我加了两层反思：工具级——失败时自动换策略重试，比如 calculate 报错就切 sql_query；答案级——用 LLM 自检覆盖度，不达标就带缺失要点反馈重跑 Agent。最多 2 轮，平衡质量和成本。"
