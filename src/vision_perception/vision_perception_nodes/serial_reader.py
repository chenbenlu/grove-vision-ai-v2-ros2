"""USB serial reader for Grove Vision AI V2 (SSCMA JSON-over-CDC)."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

try:
    import serial  # PySerial
except ImportError:  # pragma: no cover - serial is a runtime dep
    serial = None  # type: ignore[assignment]

from vision_perception_nodes._types import RawDetection


# SSCMA AT command to start continuous, unfiltered inference with no saving.
INVOKE_CMD = b"AT+INVOKE=-1,0,0\r\n"
# Marker emitted by firmware after boot, signalling the AT processor is up.
READY_MARKER = "is_ready"


class SerialUnavailable(RuntimeError):
    """Raised when the serial port cannot be opened."""


class SerialVisionReader:
    """Read newline-delimited JSON detection frames over USB-CDC."""

    def __init__(
        self,
        port: str,
        baud_rate: int,
        read_timeout_s: float = 0.05,
        init_timeout_s: float = 8.0,
        class_name_lut: Optional[Dict[int, str]] = None,
    ) -> None:
        if serial is None:
            raise SerialUnavailable("pyserial is not installed on this system")

        self._port = port
        self._read_timeout_s = read_timeout_s
        self._class_name_lut = class_name_lut or {}

        # Open without toggling DTR/RTS — those lines are wired to the Himax
        # WE2 reset on Grove Vision AI V2, so a stock `serial.Serial(...)`
        # leaves the firmware stuck in the X-Modem bootloader.
        try:
            ser = serial.Serial()
            ser.port = port
            ser.baudrate = baud_rate
            ser.timeout = 0.5  # init phase uses longer per-line wait
            ser.dtr = False
            ser.rts = False
            ser.open()
        except (serial.SerialException, FileNotFoundError, PermissionError) as exc:
            raise SerialUnavailable(
                f"cannot open serial port {port}: {exc}"
            ) from exc
        self._ser = ser

        self._initialize(init_timeout_s)
        self._ser.timeout = read_timeout_s

    def _initialize(self, timeout_s: float) -> None:
        """Drain bootloader noise and kick the SSCMA INVOKE loop."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            line = self._ser.readline()
            if not line:
                continue
            if READY_MARKER in line.decode("utf-8", errors="replace"):
                break
        # Best-effort: send the AT command whether or not we saw is_ready.
        # Some firmwares free-run without it; others stall until they get it.
        try:
            self._ser.write(INVOKE_CMD)
            self._ser.flush()
        except serial.SerialException:
            # Caller will see this as a transient read failure later.
            pass

    def close(self) -> None:
        """Release the serial handle."""
        try:
            if self._ser.is_open:
                self._ser.close()
        except Exception:  # noqa: BLE001 - best-effort shutdown
            pass

    def read_detections(self) -> Optional[List[RawDetection]]:
        """Read one JSON line; return ``None`` on timeout/transient errors."""
        try:
            raw = self._ser.readline()
        except serial.SerialException:
            return None

        if not raw:
            return None  # timeout, no data available this tick

        try:
            text = raw.decode("utf-8", errors="replace").strip()
        except UnicodeDecodeError:
            return None

        if not text:
            return None

        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            # boot-time debug noise or partial line — ignore.
            return None

        return _parse_payload(decoded, self._class_name_lut)


def _parse_payload(
    decoded: Any, class_name_lut: Dict[int, str]
) -> List[RawDetection]:
    """Extract detections from any of the SSCMA JSON shapes we have seen."""
    if not isinstance(decoded, dict):
        return []

    # Shape A: nested data.boxes
    data = decoded.get("data")
    if isinstance(data, dict) and isinstance(data.get("boxes"), list):
        return _parse_box_list(data["boxes"], class_name_lut)

    # Shape B: top-level boxes
    if isinstance(decoded.get("boxes"), list):
        return _parse_box_list(decoded["boxes"], class_name_lut)

    # Shape C: top-level detections dicts
    if isinstance(decoded.get("detections"), list):
        return _parse_detection_dicts(decoded["detections"], class_name_lut)

    return []


def _parse_box_list(
    boxes: list, class_name_lut: Dict[int, str]
) -> List[RawDetection]:
    """SSCMA box list: [center_x, center_y, w, h, score(0-100), target_id]."""
    result: List[RawDetection] = []
    for box in boxes:
        if not isinstance(box, (list, tuple)) or len(box) < 6:
            continue
        try:
            cx, cy, w, h, score, target = (int(v) for v in box[:6])
        except (TypeError, ValueError):
            continue

        x = max(0, cx - w // 2)
        y = max(0, cy - h // 2)
        result.append(
            RawDetection(
                class_id=target,
                class_name=class_name_lut.get(target, str(target)),
                confidence=score / 100.0,
                bbox_x=x,
                bbox_y=y,
                bbox_w=w,
                bbox_h=h,
            )
        )
    return result


def _parse_detection_dicts(
    items: list, class_name_lut: Dict[int, str]
) -> List[RawDetection]:
    """Dict-of-dict form (older sample protocol)."""
    result: List[RawDetection] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            class_id = int(item["id"])
            confidence = float(item["conf"])
        except (KeyError, TypeError, ValueError):
            continue
        result.append(
            RawDetection(
                class_id=class_id,
                class_name=str(item.get("name") or class_name_lut.get(class_id, str(class_id))),
                confidence=confidence,
                bbox_x=int(item.get("x", 0)),
                bbox_y=int(item.get("y", 0)),
                bbox_w=int(item.get("w", 0)),
                bbox_h=int(item.get("h", 0)),
            )
        )
    return result
