#!/usr/bin/env python3
"""ROS 2 node that publishes Grove Vision AI V2 detections to /perception/road_signs."""

from __future__ import annotations

from typing import Dict, List, Optional, Protocol, Tuple

import rclpy
from rclpy.node import Node

from vision_perception.msg import VisionAI

from vision_perception_nodes._mock_source import MockSource
from vision_perception_nodes._types import RawDetection, to_vision_ai_msg
from vision_perception_nodes.serial_reader import (
    SerialUnavailable,
    SerialVisionReader,
)


TOPIC = "/perception/road_signs"
FRAME_ID = "vision_ai"
LOW_CONF_STREAK_WARN = 10


class _Source(Protocol):
    def read_detections(self) -> Optional[List[RawDetection]]: ...


class VisionAINode(Node):
    """Polls the vision module and publishes filtered detections."""

    def __init__(self) -> None:
        super().__init__("vision_ai_node")

        self.declare_parameter("serial_port", "/dev/ttyACM0")
        self.declare_parameter("baud_rate", 921600)
        self.declare_parameter("confidence_threshold", 0.6)
        self.declare_parameter("poll_rate_hz", 20.0)
        self.declare_parameter("fallback_to_mock", True)
        # class_names is a positional list; index == class_id from firmware.
        self.declare_parameter("class_names", [""])

        port = str(self.get_parameter("serial_port").value)
        baud = int(self.get_parameter("baud_rate").value)
        self._threshold = float(self.get_parameter("confidence_threshold").value)
        rate_hz = float(self.get_parameter("poll_rate_hz").value)
        fallback = bool(self.get_parameter("fallback_to_mock").value)
        class_names = list(self.get_parameter("class_names").value or [])
        class_name_lut = {
            idx: name for idx, name in enumerate(class_names) if name
        }

        # Keep serial readline shorter than one tick so timer isn't starved.
        read_timeout = min(0.05, 1.0 / max(rate_hz, 1.0) / 2)
        self._source = self._build_source(
            port, baud, read_timeout, fallback, class_name_lut
        )
        self._publisher = self.create_publisher(VisionAI, TOPIC, 10)
        self._timer = self.create_timer(1.0 / max(rate_hz, 1.0), self._tick)

        self._last_class_ids: Tuple[int, ...] = ()
        self._low_conf_streak: int = 0

    def _build_source(
        self,
        port: str,
        baud: int,
        read_timeout_s: float,
        fallback: bool,
        class_name_lut: Dict[int, str],
    ) -> _Source:
        try:
            reader = SerialVisionReader(
                port=port,
                baud_rate=baud,
                read_timeout_s=read_timeout_s,
                class_name_lut=class_name_lut,
            )
            self.get_logger().info(
                f"Connected to Grove Vision AI V2 on {port} @ {baud}"
            )
            return reader
        except SerialUnavailable as exc:
            if not fallback:
                raise
            self.get_logger().warn(
                f"Serial unavailable ({exc}); switching to mock detection source."
            )
            return MockSource()

    def _tick(self) -> None:
        raw = self._source.read_detections()
        if raw is None:
            return  # No new frame this tick — timeout or transient error.

        accepted: List[RawDetection] = []
        rejected_low_conf = False
        for det in raw:
            if det.confidence >= self._threshold:
                accepted.append(det)
            else:
                rejected_low_conf = True

        self._publisher.publish(
            to_vision_ai_msg(accepted, FRAME_ID, self.get_clock().now().to_msg())
        )
        self._maybe_log(accepted, rejected_low_conf)

    def _maybe_log(
        self, accepted: List[RawDetection], rejected_low_conf: bool
    ) -> None:
        class_ids = tuple(sorted(d.class_id for d in accepted))
        if class_ids and class_ids != self._last_class_ids:
            names = ", ".join(f"{d.class_name}({d.confidence:.2f})" for d in accepted)
            self.get_logger().info(f"New road sign(s): {names}")
            self._last_class_ids = class_ids
            self._low_conf_streak = 0
            return

        if not accepted and self._last_class_ids:
            self.get_logger().info("Road sign cleared")
            self._last_class_ids = ()
            self._low_conf_streak = 0
            return

        if rejected_low_conf and not accepted:
            self._low_conf_streak += 1
            if self._low_conf_streak == LOW_CONF_STREAK_WARN:
                self.get_logger().warn(
                    "Persistent low-confidence detections; check lighting "
                    "or lower confidence_threshold."
                )
        else:
            self._low_conf_streak = 0


def main(args=None) -> None:
    rclpy.init(args=args)
    node = VisionAINode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
