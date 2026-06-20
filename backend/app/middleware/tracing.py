"""
OpenTelemetry tracing middleware and instrumentation utilities.
Provides distributed tracing, span enrichment, and worker instrumentation.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable, Generator

import structlog
from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

log = structlog.get_logger(__name__)
tracer = trace.get_tracer("cisco-security-platform")


# ── Span helpers ───────────────────────────────────────────────────────────────

@contextmanager
def traced(
    operation: str,
    attributes: dict[str, Any] | None = None,
) -> Generator[Span, None, None]:
    """Context manager for manual span creation with automatic error recording."""
    with tracer.start_as_current_span(operation) as span:
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, str(v))
        try:
            yield span
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            raise


def get_trace_context() -> dict[str, str]:
    """Extract current trace/span IDs for log correlation."""
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx and ctx.is_valid:
        return {
            "trace_id": format(ctx.trace_id, "032x"),
            "span_id": format(ctx.span_id, "016x"),
        }
    return {}


# ── Worker instrumentation ─────────────────────────────────────────────────────

def instrument_celery_task(task_name: str) -> Callable:
    """
    Decorator to add OpenTelemetry tracing and Prometheus metrics to Celery tasks.
    Usage: @instrument_celery_task("my_task")
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            import time
            from app.core.metrics import WORKER_TASKS_TOTAL, WORKER_TASK_DURATION

            start = time.monotonic()
            with tracer.start_as_current_span(f"celery.task.{task_name}") as span:
                span.set_attribute("celery.task.name", task_name)
                try:
                    result = func(*args, **kwargs)
                    WORKER_TASKS_TOTAL.labels(task_name=task_name, status="success").inc()
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as exc:
                    WORKER_TASKS_TOTAL.labels(task_name=task_name, status="failed").inc()
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    span.record_exception(exc)
                    raise
                finally:
                    duration = time.monotonic() - start
                    WORKER_TASK_DURATION.labels(task_name=task_name).observe(duration)

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator


# ── SIEM pipeline instrumentation ─────────────────────────────────────────────

async def traced_siem_emit(pipeline, event) -> None:
    """Emit a SIEM event with tracing span."""
    with tracer.start_as_current_span("siem.emit") as span:
        span.set_attribute("siem.event_type", event.event_type.value)
        span.set_attribute("siem.severity", event.severity.value)
        if event.device_id:
            span.set_attribute("siem.device_id", event.device_id)
        await pipeline.emit(event)


# ── Compliance engine instrumentation ─────────────────────────────────────────

async def traced_compliance_eval(orchestrator, **kwargs) -> Any:
    """Run compliance evaluation with tracing span."""
    frameworks = [f.value for f in kwargs.get("frameworks", [])]
    with tracer.start_as_current_span("compliance.evaluate_device") as span:
        span.set_attribute("compliance.device_id", str(kwargs.get("device_id", "")))
        span.set_attribute("compliance.frameworks", str(frameworks))
        report = await orchestrator.evaluate_device(**kwargs)
        span.set_attribute("compliance.score", float(report.overall_score))
        span.set_attribute("compliance.pass_count", report.pass_count)
        span.set_attribute("compliance.fail_count", report.fail_count)
        span.set_attribute("compliance.critical_failures", len(report.critical_failures))
        return report
