# Prompt 版本管理设计

> 散落在代码中的 prompt 集中管理，支持版本化、模板变量、回滚、A/B 测试。

## 背景

当前 prompt 分散在多个文件中：
- `rag/query_rewriter.py` — `REWRITE_PROMPT`
- `rag/agent.py` — `ROUTER_PROMPT` + Agent system prompt
- `rag/generator.py` — 无独立 prompt（由调用方传入）

问题：
1. 改 prompt 后效果变差无法回滚
2. 无法对比不同 prompt 版本的效果
3. prompt 和代码耦合，修改需要改代码

## 设计

新建 `rag/prompt_manager.py` + `prompts/` 目录，将 prompt 从代码中抽离。

### Prompt 文件格式（YAML）

```yaml
name: rewrite
version: 2
description: 查询改写 prompt
changelog:
  - version: 2
    date: 2026-05-29
    change: 补充"保留技术术语"规则
  - version: 1
    date: 2026-05-23
    change: 初始版本
template: |
  你是一个查询改写助手。请将用户的口语化问题改写为更正式、更精确的书面语问法。

  规则：
  1. 保留所有技术术语不变（如 mTLS、Kubernetes、API 等）
  2. 将口语表达转为专业表达（如"挂了"→"故障/失败"，"咋办"→"如何处理"）
  3. 补充缺失的主语使问题更明确（如"怎么配置"→"如何配置 XXX"）
  4. 只输出改写后的问题，不要解释

  问题：{question}
```

### PromptManager 核心 API

```python
class PromptManager:
    def __init__(self, prompts_dir: str = "prompts"):
        self.prompts_dir = prompts_dir

    def get(self, name: str, version: int | None = None) -> str:
        """加载 prompt 模板。version=None 时加载最新版本。"""

    def render(self, name: str, version: int | None = None, **kwargs) -> str:
        """加载并渲染模板变量。"""

    def list_versions(self, name: str) -> list[dict]:
        """列出 prompt 的所有版本。"""

    def ab_test(self, name: str, versions: list[int], question: str, pipeline) -> dict:
        """A/B 测试：同一问题跑多个 prompt 版本，对比效果。"""
```

### A/B 测试

```python
def ab_test(self, name: str, versions: list[int], question: str, pipeline) -> dict:
    """对比不同 prompt 版本的效果。"""
    results = {}
    for v in versions:
        prompt = self.render(name, version=v, question=question)
        # 用该 prompt 版本跑查询
        answer = pipeline.query_with_custom_prompt(question, prompt)
        results[v] = {
            "answer": answer.answer,
            "latency_ms": answer.latency_ms,
        }
    return results
```

### Prompt 文件清单

| 文件 | 对应代码 | 说明 |
|------|---------|------|
| `prompts/rewrite.yaml` | `query_rewriter.py` | 查询改写 |
| `prompts/router.yaml` | `agent.py` | 路由判断 |
| `prompts/agent_system.yaml` | `agent.py` | Agent 系统提示 |
| `prompts/quality_check.yaml` | `agent.py`（新增） | 答案自检（配合反思机制） |
| `prompts/generate.yaml` | `generator.py` | 生成回答 |

## 文件结构

| 文件 | 操作 | 说明 |
|------|------|------|
| `rag/prompt_manager.py` | 新建 | Prompt 管理器 |
| `prompts/*.yaml` | 新建 | Prompt 模板文件 |
| `rag/query_rewriter.py` | 修改 | 用 prompt_manager 加载 prompt |
| `rag/agent.py` | 修改 | 用 prompt_manager 加载 prompt |
| `rag/generator.py` | 修改 | 支持自定义 prompt |
| `tests/test_prompt_manager.py` | 新建 | 管理器测试 |

## 测试策略

| 测试 | 验证内容 |
|------|---------|
| 加载最新版本 | version=None 加载最高版本号 |
| 加载指定版本 | version=1 加载 v1 |
| 模板变量渲染 | `{question}` 被替换为实际问题 |
| 版本列表 | list_versions 返回所有版本信息 |
| 不存在的 prompt | 抛出明确错误 |
| A/B 测试 | 两个版本返回不同结果 |

## 面试话术

"Prompt 我做了版本管理：YAML 文件化存储，每个 prompt 有版本号和变更日志；模板变量注入，代码和 prompt 解耦；支持回滚——效果变差可以切回历史版本；A/B 测试——同一问题跑两个版本对比 Hit Rate，用数据驱动 prompt 优化。"
