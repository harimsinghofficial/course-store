"""Sole job: append one entry to logs/timing.jsonl per successful execution."""
from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict

from library.config import load_config, resolve

_LOCK = threading.Lock()


@dataclass
class TimingEntry:
    ts: str
    task_id: str
    context: str
    steps: Dict[str, Any]
    total_s: float


def write(task_id: str, context: str, steps: Dict[str, Any], total_s: float) -> None:
    entry = TimingEntry(
        ts=datetime.now(timezone.utc).isoformat(),
        task_id=task_id,
        context=context,
        steps=steps,
        total_s=total_s,
    )
    path = resolve(load_config()["logs"]["timing_file"])
    os.makedirs(path.parent, exist_ok=True)
    with _LOCK, open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(entry)) + "\n")
