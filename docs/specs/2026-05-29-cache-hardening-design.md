# 缓存加固设计

> 防穿透、防雪崩、防热点，让 ResultCache 具备生产级防护能力。

## 背景

当前 `ResultCache`（`rag/resilience.py`）是内存 dict + TTL + 线程安全 + 大小限制 1000。问题：

1. **穿透** — 恶意请求大量不存在的 key，每次穿透到 LLM，耗尽资源
2. **雪崩** — 大量缓存同时过期，瞬间全部打到后端
3. **热点** — 少数热门问题频繁访问，单点压力大

## 设计

在现有 `ResultCache` 基础上加固，不换架构。

### 防穿透：布隆过滤器前置

用 `pybloom_live` 或手写位数组实现布隆过滤器：

- `set()` 时同时插入布隆过滤器
- `get()` 时先查布隆过滤器，key 不存在直接返回 None
- 误判率设置 1%，空间效率高

```python
class ResultCache:
    def __init__(self, ...):
        self._bloom = BloomFilter(capacity=10000, error_rate=0.01)

    def get(self, question: str):
        key = self._key(question)
        if key not in self._bloom:  # 快速拦截
            return None
        # ... 原有逻辑
```

### 防雪崩：TTL 随机偏移

TTL 加 ±10% 随机偏移，不让大量 key 同时过期：

```python
def set(self, question: str, answer: str):
    jitter = random.uniform(-0.1, 0.1) * self.ttl
    expire_time = time.time() + self.ttl + jitter
    self._store[key] = (answer, expire_time)
```

### 防热点：热点 key 永不过期 + 异步刷新

- 访问次数超过阈值（如 10 次）的 key 标记为热点
- 热点 key 过期后返回旧值，后台异步刷新
- 用 `collections.Counter` 跟踪访问次数

```python
def get(self, question: str):
    key = self._key(question)
    self._access_count[key] += 1
    if key in self._store:
        answer, expire_time = self._store[key]
        if time.time() < expire_time:
            return answer
        if self._access_count[key] >= self.hot_threshold:
            # 热点 key：返回旧值 + 异步标记需刷新
            self._stale_keys.add(key)
            return answer
        del self._store[key]
    return None
```

## 文件结构

| 文件 | 操作 | 说明 |
|------|------|------|
| `rag/resilience.py` | 修改 | 增强 ResultCache |
| `rag/pipeline.py` | 修改 | 集成缓存（query 方法） |
| `tests/test_resilience.py` | 修改 | 新增缓存加固测试 |

## 测试策略

| 测试 | 验证内容 |
|------|---------|
| 布隆过滤器拦截不存在的 key | 未 set 过的 key 直接返回 None，不查 dict |
| TTL 随机偏移 | 同时 set 的多个 key，过期时间不同 |
| 热点 key 返回旧值 | 访问超阈值后，过期仍返回旧值 |
| 热点 key 异步刷新 | stale_keys 集合中包含需刷新的 key |
| 缓存命中率统计 | total/hit/miss 计数 |

## 面试话术

"缓存我做了三层防护：布隆过滤器防穿透——不存在的 key 直接拦截，不打到后端；TTL 随机偏移防雪崩——同批 key 不同时过期；热点 key 永不过期+异步刷新——高频访问的 key 不会因过期导致缓存击穿。"
