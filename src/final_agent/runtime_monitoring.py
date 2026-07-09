"""In-process runtime monitoring for local UI/API sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


@dataclass
class RuntimeMonitor:
    """Collect lightweight runtime metrics without external services."""

    _lock: Lock = field(default_factory=Lock)
    _retrieval_count: int = 0
    _retrieval_latency_ms: float = 0.0
    _retrieval_scoped_queries: int = 0
    _retrieval_hits: int = 0
    _retrieval_results: int = 0
    _model_call_count: int = 0
    _model_latency_ms: float = 0.0
    _prompt_tokens: int = 0
    _completion_tokens: int = 0
    _estimated_cost_usd: float = 0.0

    def record_retrieval(
        self,
        *,
        latency_ms: float,
        course_ids: list[str] | None,
        result_course_ids: list[str],
    ) -> None:
        scoped = [course_id for course_id in (course_ids or []) if course_id]
        scoped_set = set(scoped)
        hit_count = (
            sum(1 for course_id in result_course_ids if course_id in scoped_set)
            if scoped_set
            else len(result_course_ids)
        )
        with self._lock:
            self._retrieval_count += 1
            self._retrieval_latency_ms += latency_ms
            self._retrieval_results += len(result_course_ids)
            self._retrieval_hits += hit_count
            if scoped:
                self._retrieval_scoped_queries += 1

    def record_model_call(
        self,
        *,
        provider: str,
        model: str,
        latency_ms: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        estimated_cost_usd: float = 0.0,
    ) -> None:
        del provider, model
        with self._lock:
            self._model_call_count += 1
            self._model_latency_ms += latency_ms
            self._prompt_tokens += prompt_tokens
            self._completion_tokens += completion_tokens
            self._estimated_cost_usd += estimated_cost_usd

    def snapshot(self) -> dict[str, dict[str, float | int]]:
        with self._lock:
            retrieval_avg = (
                self._retrieval_latency_ms / self._retrieval_count
                if self._retrieval_count
                else 0.0
            )
            hit_rate = (
                self._retrieval_hits / self._retrieval_results
                if self._retrieval_results
                else 0.0
            )
            model_avg = (
                self._model_latency_ms / self._model_call_count
                if self._model_call_count
                else 0.0
            )
            return {
                "retrieval": {
                    "count": self._retrieval_count,
                    "avg_latency_ms": retrieval_avg,
                    "course_hit_rate": hit_rate,
                    "scoped_queries": self._retrieval_scoped_queries,
                },
                "model_calls": {
                    "count": self._model_call_count,
                    "avg_latency_ms": model_avg,
                    "prompt_tokens": self._prompt_tokens,
                    "completion_tokens": self._completion_tokens,
                    "estimated_cost_usd": self._estimated_cost_usd,
                },
            }


_RUNTIME_MONITOR = RuntimeMonitor()


def get_runtime_monitor() -> RuntimeMonitor:
    return _RUNTIME_MONITOR


def reset_runtime_monitor() -> None:
    global _RUNTIME_MONITOR
    _RUNTIME_MONITOR = RuntimeMonitor()
