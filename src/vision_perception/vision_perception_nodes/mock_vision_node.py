#!/usr/bin/env python3
"""PC-side mock that emits synthetic Grove Vision AI V2 detections."""

from __future__ import annotations

from typing import List, Tuple

import rclpy
from rclpy.node import Node

from vision_perception.msg import VisionAI

from vision_perception_nodes._mock_source import MockSource
from vision_perception_nodes._types import RawDetection, to_vision_ai_msg


TOPIC = "/perception/road_signs"
FRAME_ID = "mock_vision"


class MockVisionNode(Node):
    """Publishes fake road-sign detections so upper-stack nodes can be tested."""

    def __init__(self) -> None:
        super().__init__("mock_vision_node")

        self.declare_parameter("confidence_threshold", 0.6)
        self.declare_parameter("poll_rate_hz", 5.0)
        self.declare_parameter("change_every_frames", 5)

        self._threshold = float(self.get_parameter("confidence_threshold").value)
        rate_hz = float(self.get_parameter("poll_rate_hz").value)
        change_every = int(self.get_parameter("change_every_frames").value)

        self._source = MockSource(change_every_frames=change_every)
        self._publisher = self.create_publisher(VisionAI, TOPIC, 10)
        self._timer = self.create_timer(1.0 / max(rate_hz, 1.0), self._tick)
        self._last_class_ids: Tuple[int, ...] = ()

        self.get_logger().info(
            "mock_vision_node started — publishing synthetic detections to "
            f"{TOPIC} at {rate_hz:.1f} Hz"
        )

    def _tick(self) -> None:
        raw: List[RawDetection] = self._source.read_detections() or []
        accepted = [d for d in raw if d.confidence >= self._threshold]

        self._publisher.publish(
            to_vision_ai_msg(accepted, FRAME_ID, self.get_clock().now().to_msg())
        )

        class_ids = tuple(sorted(d.class_id for d in accepted))
        if class_ids != self._last_class_ids:
            if accepted:
                names = ", ".join(
                    f"{d.class_name}({d.confidence:.2f})" for d in accepted
                )
                self.get_logger().info(f"[mock] sign change → {names}")
            else:
                self.get_logger().info("[mock] sign cleared")
            self._last_class_ids = class_ids


def main(args=None) -> None:
    rclpy.init(args=args)
    node = MockVisionNode()
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
