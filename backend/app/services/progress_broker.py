"""
进度 Broker —— 多 Agent 图执行期间的实时事件总线（SSE 的数据源）。

问题：LangGraph 图是同步阻塞的，节点产出的 progress_events 只有在
invoke 全部结束后才能拿到，前端只能轮询、看不到实时进度。

方案：图执行线程边跑边把进度事件 publish 到本 Broker；SSE 接口 subscribe
后先重放缓冲（避免漏掉订阅前的事件，任务已结束时也能拿到完整历史），
再持续收到实时事件，直到图结束 publish 终止标记为止。

线程安全：用 threading.Lock 保护缓冲与订阅者列表；SSE 侧通过
asyncio.to_thread(queue.get) 阻塞读取，不占用事件循环。
"""
from __future__ import annotations

import threading
from queue import Empty, Queue
from typing import Any

# 内部终止事件（不直接推给前端）；SSE 遇到即关闭
END_EVENT: dict = {"type": "end"}
# 实时订阅队列里的哨兵（用唯一对象，避免与 None/空事件混淆）
_SENTINEL: Any = object()


class ProgressBroker:
    """按 task_id 分组的发布/订阅总线，带缓冲重放。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buffers: dict[str, list[dict]] = {}
        self._subscribers: dict[str, list[Queue]] = {}
        self._closed: set[str] = set()

    def open(self, task_id: str) -> None:
        """图执行开始前调用：建立缓冲。"""
        with self._lock:
            self._buffers.setdefault(task_id, [])
            self._closed.discard(task_id)

    def publish(self, task_id: str, event: dict) -> None:
        """发布一个事件（同时进缓冲与各实时订阅队列）。"""
        with self._lock:
            self._buffers.setdefault(task_id, []).append(event)
            for q in self._subscribers.get(task_id, []):
                q.put(event)

    def subscribe(self, task_id: str) -> Queue:
        """订阅某任务的进度流：先重放已缓冲事件，再收实时事件。

        任务已结束时，队列只含重放历史 + 哨兵，不注册为实时订阅者。
        """
        q: Queue = Queue()
        with self._lock:
            for ev in self._buffers.get(task_id, []):
                q.put(ev)
            if task_id in self._closed:
                q.put(_SENTINEL)
            else:
                self._subscribers.setdefault(task_id, []).append(q)
        return q

    def unsubscribe(self, task_id: str, q: Queue) -> None:
        """SSE 断开时清理订阅。"""
        with self._lock:
            subs = self._subscribers.get(task_id)
            if subs and q in subs:
                subs.remove(q)

    def close(self, task_id: str) -> None:
        """图执行结束后调用：追加终止事件，向实时订阅者投递哨兵。"""
        with self._lock:
            self._buffers.setdefault(task_id, []).append(END_EVENT)
            self._closed.add(task_id)
            for q in self._subscribers.get(task_id, []):
                q.put(_SENTINEL)
            self._subscribers.pop(task_id, None)

    def purge(self, task_id: str) -> None:
        """删除任务时清理缓冲与订阅。"""
        with self._lock:
            self._buffers.pop(task_id, None)
            self._subscribers.pop(task_id, None)
            self._closed.discard(task_id)

    @staticmethod
    def is_sentinel(item: Any) -> bool:
        return item is _SENTINEL

    @staticmethod
    def get_nowait(q: Queue, timeout: float = 0.05) -> Any:
        """非阻塞取一条；队列空返回 None。"""
        try:
            return q.get(timeout=timeout)
        except Empty:
            return None


# 单例
_broker = ProgressBroker()


def get_progress_broker() -> ProgressBroker:
    return _broker
