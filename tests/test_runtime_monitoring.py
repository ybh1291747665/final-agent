from __future__ import annotations


def test_runtime_monitor_records_retrieval_latency_and_course_hits():
    from final_agent.runtime_monitoring import RuntimeMonitor

    monitor = RuntimeMonitor()

    monitor.record_retrieval(
        latency_ms=42.5,
        course_ids=["course-a"],
        result_course_ids=["course-a", "course-b", "course-a"],
    )

    snapshot = monitor.snapshot()

    assert snapshot["retrieval"]["count"] == 1
    assert snapshot["retrieval"]["avg_latency_ms"] == 42.5
    assert snapshot["retrieval"]["course_hit_rate"] == 2 / 3
    assert snapshot["retrieval"]["scoped_queries"] == 1


def test_runtime_monitor_records_model_call_costs():
    from final_agent.runtime_monitoring import RuntimeMonitor

    monitor = RuntimeMonitor()

    monitor.record_model_call(
        provider="deepseek",
        model="deepseek-v4-flash",
        latency_ms=120.0,
        prompt_tokens=1000,
        completion_tokens=500,
        estimated_cost_usd=0.0025,
    )

    snapshot = monitor.snapshot()

    assert snapshot["model_calls"]["count"] == 1
    assert snapshot["model_calls"]["avg_latency_ms"] == 120.0
    assert snapshot["model_calls"]["prompt_tokens"] == 1000
    assert snapshot["model_calls"]["completion_tokens"] == 500
    assert snapshot["model_calls"]["estimated_cost_usd"] == 0.0025


def test_global_runtime_monitor_can_be_reset_between_tests():
    from final_agent.runtime_monitoring import get_runtime_monitor, reset_runtime_monitor

    get_runtime_monitor().record_retrieval(
        latency_ms=10.0,
        course_ids=[],
        result_course_ids=[],
    )

    reset_runtime_monitor()

    assert get_runtime_monitor().snapshot()["retrieval"]["count"] == 0
