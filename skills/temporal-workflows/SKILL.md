---
name: temporal-workflows
description: Guide and best practices for developing, testing, and debugging Temporal Python workflows, activities, signals, queries, and OpenTelemetry instrumentation.
---

# Temporal Workflows Skill Guide

This skill provides reference patterns and guidelines for writing robust, scalable Temporal workflows in Python.

## 1. Core Workflow Determinism Rules

Temporal workflows must be **strictly deterministic** because Temporal rebuilds workflow state by replaying event history.

### What is FORBIDDEN inside `@workflow.defn`:
1. **No direct I/O**: Do NOT read/write files, make HTTP requests, or query databases directly. Use `@activity.defn` for all I/O.
2. **No native threads or asynchronous tasks**: Do NOT use `threading.Thread`, `multiprocessing`, or `asyncio.create_task` directly. Use `workflow.start_activity()` or `workflow.wait_condition()`.
3. **No non-deterministic functions**:
   - Do NOT call `datetime.now()` or `time.time()`. Use `workflow.now()`.
   - Do NOT call `random.random()` or `uuid.uuid4()`. Use `workflow.uuid4()`.
4. **Use Unsafe Imports Sparingly**:
   ```python
   with workflow.unsafe.imports_passed_through():
       import pydantic_models
   ```

---

## 2. Activity Best Practices

Activities perform the non-deterministic real work: network calls, SQL queries, machine learning, and data processing.

### Activity Timeouts & Retries
Always configure `start_to_close_timeout` and a clear `RetryPolicy`:
```python
from datetime import timedelta
from temporalio.common import RetryPolicy

retry_policy = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
    maximum_attempts=5,
    non_retryable_error_types=["InvalidInputError"],
)

await workflow.execute_activity(
    "deidentify_demographics_activity",
    config,
    start_to_close_timeout=timedelta(minutes=5),
    retry_policy=retry_policy,
)
```

### Heartbeating for Long-Running Tasks
For batch processing or ML inference, send heartbeats periodically so Temporal knows the worker hasn't crashed:
```python
from temporalio import activity


@activity.defn
async def process_batch_activity(items: list):
    for i, item in enumerate(items):
        activity.heartbeat(f"Processed {i}/{len(items)}")
        # process item...
```

---

## 3. Workflow Queries & Signals

### Queries (Read-only status inspection)
Inspect running workflows without modifying their state:
```python
@workflow.defn
class MyWorkflow:
    def __init__(self):
        self._progress = 0

    @workflow.query
    def get_progress(self) -> int:
        return self._progress
```

### Signals (Asynchronous external input)
Send signals to pause, resume, cancel, or inject human approval:
```python
@workflow.signal
def pause_pipeline(self) -> None:
    self._paused = True


@workflow.signal
def resume_pipeline(self) -> None:
    self._paused = False
```

---

## 4. OpenTelemetry Distributed Tracing

Temporal Python SDK integrates natively with OpenTelemetry via `TracingInterceptor`:
```python
from temporalio.client import Client
from temporalio.contrib.opentelemetry import TracingInterceptor

client = await Client.connect(
    "localhost:7233",
    interceptors=[TracingInterceptor()],
)
```
Every workflow start, activity start, retry, and completion will emit correlated OpenTelemetry spans.

---

## 5. In-Memory Testing with WorkflowEnvironment

In automated test suites (`pytest`), avoid running an external Temporal server by using Temporal's built-in time-skipping test server:
```python
import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker


@pytest.mark.asyncio
async def test_workflow():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[MyWorkflow],
            activities=[my_activity],
        ):
            handle = await env.client.start_workflow(
                "MyWorkflow",
                "test-arg",
                id="test-wf-1",
                task_queue="test-queue",
            )
            result = await handle.result()
            assert result["success"] is True
```
