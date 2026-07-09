"""In-process capture of LLM calls (system prompt + user prompt + response).

`_chat()` in llm.py is the single choke point for every LLM request, so it calls
`record()` on each call. An API endpoint wraps its LLM work in `capture(stage)`;
any calls made inside are collected and can then be persisted to `llm_runs`.

Uses a contextvar so concurrent requests never mix (each request/task has its own
context; `_chat` is awaited directly within the endpoint's task).
"""
from __future__ import annotations

import contextvars
from contextlib import contextmanager

_current: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "llm_capture", default=None
)


@contextmanager
def capture(stage: str):
    """Collect every LLM call made within this block. Yields the entry list."""
    sink: dict = {"stage": stage, "entries": []}
    token = _current.set(sink)
    try:
        yield sink["entries"]
    finally:
        _current.reset(token)


def record(system: str, user: str, response: str) -> None:
    sink = _current.get()
    if sink is not None:
        sink["entries"].append(
            {"system": system, "user": user, "response": response}
        )
