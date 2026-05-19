"""Shared data types and msg conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from builtin_interfaces.msg import Time

from vision_perception.msg import Detection, VisionAI


@dataclass
class RawDetection:
    """One detection in node-internal form (before conversion to ROS msg)."""

    class_id: int
    class_name: str
    confidence: float
    bbox_x: int
    bbox_y: int
    bbox_w: int
    bbox_h: int


def _to_detection_msg(d: RawDetection) -> Detection:
    return Detection(
        class_id=d.class_id,
        class_name=d.class_name,
        confidence=d.confidence,
        bbox_x=d.bbox_x,
        bbox_y=d.bbox_y,
        bbox_w=d.bbox_w,
        bbox_h=d.bbox_h,
    )


def to_vision_ai_msg(
    detections: List[RawDetection], frame_id: str, stamp: Time
) -> VisionAI:
    """Build a VisionAI msg with header + Detection[] from internal records."""
    msg = VisionAI()
    msg.header.stamp = stamp
    msg.header.frame_id = frame_id
    msg.detections = [_to_detection_msg(d) for d in detections]
    return msg
