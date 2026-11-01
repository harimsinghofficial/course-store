"""Sole job: append one entry to logs/errors.jsonl per failure."""
from __future__ import annotations

import json
import os
import threading
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from library.config import load_config, resolve

_LOCK = threading.Lock()


@dataclass
class ErrorEntry:
    ts: str
    task_id: str
    context: str
    stage: str
    error: str
    traceback: str


def write(task_id: str, context: str, stage: str, exc: BaseException) -> None:
    entry = ErrorEntry(
        ts=datetime.now(timezone.utc).isoformat(),
        task_id=task_id,
        context=context,
        stage=stage,
        error=str(exc),
        traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    )
    path = resolve(load_config()["logs"]["error_file"])
    os.makedirs(path.parent, exist_ok=True)
    with _LOCK, open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(entry)) + "\n")
