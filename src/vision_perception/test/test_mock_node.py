"""Smoke test: spin the mock node once and confirm a VisionAI message arrives."""

from __future__ import annotations

import threading
import time

import pytest
import rclpy
from rclpy.executors import SingleThreadedExecutor

from vision_perception_nodes.mock_vision_node import MockVisionNode
from vision_perception.msg import VisionAI


@pytest.fixture(scope="module", autouse=True)
def _rclpy_context():
    rclpy.init()
    yield
    if rclpy.ok():
        rclpy.shutdown()


def test_mock_node_publishes_vision_ai() -> None:
    received: list[VisionAI] = []

    node = MockVisionNode()
    listener = rclpy.create_node("test_listener")
    listener.create_subscription(
        VisionAI, "/perception/road_signs", lambda msg: received.append(msg), 10
    )

    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(listener)

    stop_event = threading.Event()

    def spin() -> None:
        while not stop_event.is_set():
            executor.spin_once(timeout_sec=0.1)

    thread = threading.Thread(target=spin, daemon=True)
    thread.start()

    deadline = time.time() + 3.0
    while time.time() < deadline and not received:
        time.sleep(0.05)

    stop_event.set()
    thread.join(timeout=2.0)
    executor.shutdown()
    node.destroy_node()
    listener.destroy_node()

    assert received, "mock_vision_node did not publish within 3s"
    # detections is a sequence (may be empty when current sign is 'none')
    assert hasattr(received[0], "detections")
