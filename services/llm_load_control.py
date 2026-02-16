import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict


@dataclass(frozen=True)
class LLMGateSnapshot:
    enabled: bool
    limits: Dict[str, int]
    in_window_calls: Dict[str, int]
    dropped_calls: Dict[str, int]

    def to_dict(self) -> Dict[str, object]:
        return {
            "enabled": self.enabled,
            "limits": self.limits,
            "inWindowCalls": self.in_window_calls,
            "droppedCalls": self.dropped_calls,
        }


class LLMCallGate:
    """
    In-process RPM gate for LLM calls.
    - Enforces a global per-minute limit and per-stage limits.
    - Supports behavior-call sampling to reduce load in burst scenarios.
    """

    _WINDOW_SECONDS = 60.0

    def __init__(
        self,
        *,
        enabled: bool,
        global_rpm_limit: int,
        reply_rpm_limit: int,
        behavior_rpm_limit: int,
        extraction_rpm_limit: int,
        behavior_sample_every_n_scam_messages: int,
    ):
        self._enabled = bool(enabled)
        self._global_limit = max(1, int(global_rpm_limit))
        self._stage_limits = {
            "reply": max(1, int(reply_rpm_limit)),
            "behavior": max(1, int(behavior_rpm_limit)),
            "extraction": max(1, int(extraction_rpm_limit)),
        }
        self._behavior_sample_n = max(1, int(behavior_sample_every_n_scam_messages))
        self._calls: Dict[str, Deque[float]] = {
            "global": deque(),
            "reply": deque(),
            "behavior": deque(),
            "extraction": deque(),
        }
        self._dropped: Dict[str, int] = {"reply": 0, "behavior": 0, "extraction": 0}
        self._lock = threading.Lock()

    def _prune(self, queue: Deque[float], now: float) -> None:
        cutoff = now - self._WINDOW_SECONDS
        while queue and queue[0] < cutoff:
            queue.popleft()

    def _behavior_sampling_allows(self, scammer_message_index: int) -> bool:
        if self._behavior_sample_n <= 1:
            return True
        if scammer_message_index <= 1:
            return True
        return (scammer_message_index - 1) % self._behavior_sample_n == 0

    def allow(self, stage: str, scammer_message_index: int = 0) -> bool:
        if stage not in self._stage_limits:
            return False
        if not self._enabled:
            return True

        if stage == "behavior" and not self._behavior_sampling_allows(max(0, scammer_message_index)):
            return False

        now = time.time()
        with self._lock:
            global_queue = self._calls["global"]
            stage_queue = self._calls[stage]
            self._prune(global_queue, now)
            self._prune(stage_queue, now)

            if len(global_queue) >= self._global_limit:
                self._dropped[stage] += 1
                return False
            if len(stage_queue) >= self._stage_limits[stage]:
                self._dropped[stage] += 1
                return False

            global_queue.append(now)
            stage_queue.append(now)
            return True

    def snapshot(self) -> LLMGateSnapshot:
        now = time.time()
        with self._lock:
            for queue in self._calls.values():
                self._prune(queue, now)
            return LLMGateSnapshot(
                enabled=self._enabled,
                limits={
                    "globalRpm": self._global_limit,
                    "replyRpm": self._stage_limits["reply"],
                    "behaviorRpm": self._stage_limits["behavior"],
                    "extractionRpm": self._stage_limits["extraction"],
                },
                in_window_calls={
                    "global": len(self._calls["global"]),
                    "reply": len(self._calls["reply"]),
                    "behavior": len(self._calls["behavior"]),
                    "extraction": len(self._calls["extraction"]),
                },
                dropped_calls=dict(self._dropped),
            )

