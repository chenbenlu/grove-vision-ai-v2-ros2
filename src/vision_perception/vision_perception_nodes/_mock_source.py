"""Shared mock detection source used by mock_vision_node and the fallback path."""

from __future__ import annotations

import random
from typing import List

from vision_perception_nodes._types import RawDetection


ROAD_SIGNS = [
    (0, "stop"),
    (1, "yield"),
    (2, "speed_30"),
    (3, "speed_60"),
]
EMPTY_FRAME_PROB = 0.2  # how often a tick reports no detection at all


class MockSource:
    """Emit deterministic-ish random detections for PC integration tests."""

    def __init__(self, change_every_frames: int = 20) -> None:
        self._counter = 0
        self._change_every = max(1, change_every_frames)
        self._current = random.choice(ROAD_SIGNS)

    def read_detections(self) -> List[RawDetection]:
        self._counter += 1
        if self._counter % self._change_every == 0:
            self._current = random.choice(ROAD_SIGNS)

        if random.random() < EMPTY_FRAME_PROB:
            return []

        class_id, class_name = self._current
        return [
            RawDetection(
                class_id=class_id,
                class_name=class_name,
                confidence=round(random.uniform(0.4, 0.95), 2),
                bbox_x=random.randint(0, 200),
                bbox_y=random.randint(0, 150),
                bbox_w=random.randint(30, 80),
                bbox_h=random.randint(30, 80),
            )
        ]
