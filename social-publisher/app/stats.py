"""平台数据统计：快照存储、趋势序列、分条目数据。

数据来源两种：
- API 自动采集（已配置凭据的平台，点「刷新数据」时拉取）
- 手动记录（任何平台都可以，适合无 API 的小红书/视频号等）

每次记录为一个快照，存入 stats_history.json，用于趋势图表。
"""

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HISTORY_PATH = ROOT / "stats_history.json"

METRIC_KEYS = ["followers", "likes", "comments", "favorites"]


def _load() -> list[dict]:
    if HISTORY_PATH.exists():
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    return []


def _save(rows: list[dict]) -> None:
    HISTORY_PATH.write_text(
        json.dumps(rows, ensure_ascii=False), encoding="utf-8")


def record(pid: str, metrics: dict, posts: list | None = None,
           source: str = "manual") -> None:
    rows = _load()
    rows.append({
        "ts": int(time.time()),
        "platform": pid,
        "metrics": {k: int(metrics.get(k) or 0) for k in METRIC_KEYS},
        "posts": posts or [],
        "source": source,
    })
    _save(rows)


def overview(platform_specs: dict) -> list[dict]:
    """每个平台：最新指标 + 相对上次的变化 + 历史序列 + 最新分条目。"""
    rows = _load()
    out = []
    for pid, spec in platform_specs.items():
        h = [r for r in rows if r["platform"] == pid]
        latest = h[-1] if h else None
        prev = h[-2] if len(h) > 1 else None
        delta = None
        if latest and prev:
            delta = {k: latest["metrics"][k] - prev["metrics"][k]
                     for k in METRIC_KEYS}
        # 分条目：取最近一次带条目的快照（手动记录可能不含条目）
        posts = next((r["posts"] for r in reversed(h) if r.get("posts")), [])
        out.append({
            "id": pid, "name": spec.name, "icon": spec.icon,
            "latest": latest["metrics"] if latest else None,
            "updated": latest["ts"] if latest else None,
            "source": latest["source"] if latest else None,
            "delta": delta,
            "series": [{"ts": r["ts"], **r["metrics"]} for r in h],
            "posts": posts,
        })
    return out
