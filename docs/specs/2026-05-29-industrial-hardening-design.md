# 工业级加固设计

> 补齐面试反馈中的 4 个 🔴 级缺口：容错、安全、并发、指标。从 Demo 级升级到可上线的工业级。

## 背景

面试反馈核心：Demo 跑通流程就行，工业级是能上线、稳运行、会学习、可扩展的完整系统。当前系统功能完整但缺乏生产级保障——API 调用失败直接报错、无安全防护、无并发保护、评估数据集太小。

## 1. 容错层

**目标：** 任何外部调用失败都不会让整个系统崩溃。

### 1.1 重试机制

**文件：** `rag/resilience.py`（新建）

通用重试装饰器，区分可重试和不可重试错误：

```python
@retry(max_attempts=3, backoff_base=1.0, retryable_exceptions=(Timeout, RateLimitError))
def call_api():
    ...
```

- 可重试：超时、限流（429）、服务不可用（503）
- 不可重试：认证失败（401/403）、请求格式错误（400）
- 指数退避：1s → 2s → 4s，加随机抖动防惊群

**影响范围：** `rag/generator.py`、`rag/reranker.py`、`rag/embedder.py`、`rag/query_rewriter.py`

### 1.2 熔断器

连续失败 N 次（默认 5）→ 熔断状态，直接返回 fallback，不再调用 API。

熔断 30 秒后自动进入半开状态，放一个请求探测，成功→恢复，失败→继续熔断。

```python
class CircuitBreaker:
    states: CLOSED → OPEN → HALF_OPEN → CLOSED
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
```

### 1.3 降级策略

| 组件 | 降级方案 |
|------|---------|
| reranker | 跳过重排序，直接用向量检索结果 |
| generator | 返回"系统繁忙，请稍后重试" |
| embedding | 用缓存的最近一次结果 |
| query_rewriter | 跳过改写，用原始问题检索 |

### 1.4 超时控制

每个外部调用独立超时：

| 调用 | 超时 |
|------|------|
| DeepSeek API | 10s |
| 百炼 embedding | 5s |
| 百炼 rerank | 5s |
| Qdrant 查询 | 3s |

### 1.5 结果缓存

相同问题短时间内不重复调 LLM：

- 缓存 key：问题文本的 hash
- 缓存时间：5 分钟
- 缓存位置：内存 dict（简单场景），后续可升级 Redis

## 2. 安全层

**目标：** 防止恶意输入破坏系统或泄露敏感信息。

### 2.1 Prompt Injection 防护

**文件：** `rag/guard.py`（新建）

多层检测：

| 层 | 检测内容 | 处理 |
|----|---------|------|
| 关键词 | "忽略之前的指令"、"system prompt"、"ignore previous" | 拒绝 |
| 模式 | 问题超长（>2000 字）、含大量特殊字符、角色扮演模式 | 拒绝 |
| 输出审查 | 检查 LLM 输出是否包含 system prompt 片段、内部路径、API key | 替换为 [已过滤] |

命中→返回安全提示，不传给 LLM，记录到 execution_logs（route="blocked"）。

### 2.2 输入净化

- 截断超长输入（>5000 字符）
- 去除控制字符（\x00-\x1f，保留换行）
- 限制单次请求处理的文档大小（10MB）

### 2.3 速率限制

每个 API Key 每分钟最多 N 次请求（默认 60）：

- 使用令牌桶算法
- 超限返回 429 Too Many Requests
- 记录到审计日志

### 2.4 审计日志

所有请求记录：时间、API Key、问题、路由、耗时、是否被拦截。

复用 `execution_logs` 表，新增 `client_ip` 和 `blocked_reason` 字段。

## 3. 并发层

**目标：** 多用户同时访问不崩溃、不冲突。

### 3.1 连接池

Qdrant 客户端复用，全局单例 + 线程锁保护写操作：

```python
_client_lock = threading.Lock()

def add_to_collection(...):
    with _client_lock:
        client.upsert(...)
```

读操作不需要锁（Qdrant 支持并发读）。

### 3.2 请求队列

高并发时排队处理，防止资源耗尽：

- 使用 `queue.Queue` + 工作线程池
- 队列满→返回 503 Service Unavailable
- 可配置队列大小和工作线程数

### 3.3 健康检查

`/health` 端点检查各组件状态：

```json
{
  "status": "healthy",
  "components": {
    "qdrant": "ok",
    "sqlite": "ok",
    "deepseek_api": "ok"
  }
}
```

### 3.4 线程安全

全局状态保护：

| 状态 | 保护方式 |
|------|---------|
| `_client`（Qdrant） | `threading.Lock` |
| `pipeline`（API） | 请求级别创建，无需锁 |
| `memory.db`（SQLite） | `check_same_thread=False` + WAL 模式 |

## 4. 指标层

**目标：** 有硬数据写简历，能量化每个优化的效果。

### 4.1 评估数据集扩充

当前 11 题 → 30+ 题，覆盖场景：

| 类型 | 数量 | 示例 |
|------|------|------|
| 事实问答 | 10 | "使用什么协议？" |
| 跨文档推理 | 5 | "配置下发的安全性？" |
| 口语化表达 | 5 | "服务挂了咋办？" |
| 专业术语 | 5 | "mTLS 的三种模式？" |
| 边界情况 | 5 | 空问题、超长问题、无关问题 |

### 4.2 回归检测

每次优化后自动对比基线：

```
基线: Hit Rate 82% (11 题)
查询改写后: Hit Rate 90.9% (+8.9%)
重排序后: Hit Rate 95% (+4.1%)
```

指标下降自动告警（打印 WARNING）。

### 4.3 多维指标

| 指标 | 说明 |
|------|------|
| Hit Rate | 答案包含期望关键词的比例 |
| 延迟 P50 | 中位延迟 |
| 延迟 P95 | 95 分位延迟 |
| Token 消耗 | 每次查询平均 token 数 |
| 缓存命中率 | 缓存命中 / 总查询 |

### 4.4 报告输出

评估报告输出为 Markdown 格式，可直接贴 GitHub README：

```markdown
## RAG 系统评估报告

| 指标 | 值 |
|------|-----|
| Hit Rate | 90.9% (10/11) |
| 平均延迟 | 7116ms |
| P95 延迟 | 12000ms |

### 失败分析
- Q7: 跨章节推理，文档未显式关联
```

### 4.5 Bad Case 库

失败用例自动归档到 `data/bad_cases.jsonl`：

```json
{"question": "...", "expected": "...", "actual": "...", "reason": "cross-chapter", "date": "2026-05-29"}
```

支持手动标注失败原因，用于迭代优化。

## 文件结构

| 文件 | 职责 | 操作 |
|------|------|------|
| `rag/resilience.py` | 重试、熔断、降级、超时、缓存 | 新建 |
| `rag/guard.py` | Prompt Injection 防护、输入净化、输出审查 | 新建 |
| `rag/concurrency.py` | 连接池、读写锁、请求队列 | 新建 |
| `rag/generator.py` | 集成重试 + 熔断 | 修改 |
| `rag/reranker.py` | 集成重试 + 降级 | 修改 |
| `rag/embedder.py` | 集成重试 | 修改 |
| `rag/vector_store.py` | 集成读写锁 | 修改 |
| `rag/pipeline.py` | 集成 guard + 缓存 | 修改 |
| `rag/api.py` | 集成速率限制 + 健康检查 | 修改 |
| `rag/eval.py` | 回归检测 + 多维指标 + Bad Case | 修改 |
| `data/eval_dataset.jsonl` | 扩充到 30+ 题 | 修改 |
| `tests/test_resilience.py` | 容错层测试 | 新建 |
| `tests/test_guard.py` | 安全层测试 | 新建 |
| `tests/test_concurrency.py` | 并发层测试 | 新建 |

## 实现顺序

1. 容错层（重试 → 熔断 → 降级 → 超时 → 缓存）
2. 安全层（guard → 输入净化 → 输出审查 → 速率限制）
3. 并发层（读写锁 → 连接池 → 健康检查）
4. 指标层（数据集扩充 → 回归检测 → 多维指标 → Bad Case）

## 面试话术

"我把系统从 Demo 级升级到工业级，主要做了四件事：容错——重试+熔断+降级，API 挂了系统不会崩；安全——Prompt Injection 防护+输入净化+输出审查；并发——读写锁+连接池，多用户同时访问不冲突；指标——30 题评估集+回归检测，每次优化能量化效果。"
