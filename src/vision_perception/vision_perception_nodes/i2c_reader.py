"""I2C reader for Grove Vision AI V2 (SSCMA-Micro FEATURE_TRANSPORT framed protocol)."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

try:
    from smbus2 import SMBus, i2c_msg
except ImportError:  # pragma: no cover - smbus2 is Pi-only
    SMBus = None  # type: ignore[assignment]
    i2c_msg = None  # type: ignore[assignment]

from vision_perception_nodes._types import RawDetection


# FEATURE / CMD constants — matches sscma-micro and Seeed_Arduino_SSCMA.
FEATURE_TRANSPORT = 0x10
CMD_READ = 0x01
CMD_WRITE = 0x02
CMD_AVAILABLE = 0x03

# I2C timing tuned to match Seeed_Arduino_SSCMA defaults.
WAIT_DELAY_S = 0.002         # 2 ms between every write/read pair
MAX_PL_LEN = 250             # Slave-side packet limit per FEATURE_TRANSPORT call
READ_BUFFER_LIMIT = 65536    # Cap on internal line buffer

# SSCMA AT command — start continuous inference, result-only (no base64 image).
INVOKE_CMD = b"AT+INVOKE=-1,0,1\r"


class I2CUnavailable(RuntimeError):
    """Raised when the I2C bus cannot be opened or the slave does not respond."""


class GroveVisionI2CReader:
    """Read SSCMA JSON events from Grove Vision AI V2 over I2C."""

    def __init__(
        self,
        bus: int,
        address: int,
        class_name_lut: Optional[Dict[int, str]] = None,
        init_timeout_s: float = 8.0,
    ) -> None:
        if SMBus is None:
            raise I2CUnavailable("smbus2 is not installed on this system")

        self._address = address
        self._class_name_lut = class_name_lut or {}
        self._buffer = bytearray()

        try:
            self._bus = SMBus(bus)
        except (FileNotFoundError, PermissionError) as exc:
            raise I2CUnavailable(f"cannot open I2C bus {bus}: {exc}") from exc

        # Probe the slave once so missing hardware fails fast. Address-only
        # quick-write matches what `i2cdetect` does — works even before any
        # FEATURE_TRANSPORT exchange.
        try:
            self._bus.write_quick(address)
        except OSError as exc:
            self._bus.close()
            raise I2CUnavailable(
                f"no slave at 0x{address:02x} on bus {bus}: {exc}"
            ) from exc

        self._initialize(init_timeout_s)

    def close(self) -> None:
        """Release the underlying bus handle."""
        try:
            self._bus.close()
        except Exception:  # noqa: BLE001 - best-effort shutdown
            pass

    def read_detections(self) -> Optional[List[RawDetection]]:
        """Drain bytes; return one line's detections or ``None`` if incomplete."""
        try:
            self._pump_into_buffer()
        except OSError:
            return None

        line = self._take_line()
        if line is None:
            return None

        try:
            decoded = json.loads(line.decode("utf-8", errors="replace"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return []

        return _parse_payload(decoded, self._class_name_lut)

    # --- private helpers ---------------------------------------------------

    def _initialize(self, timeout_s: float) -> None:
        """Drain boot noise (best-effort) and send AT+INVOKE."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                self._pump_into_buffer()
            except OSError:
                pass
            if any(
                b"is_ready" in line for line in self._buffer.split(b"\n")
            ):
                self._buffer.clear()
                break
            time.sleep(0.05)
        try:
            self._frame_write(INVOKE_CMD)
        except OSError:
            # Fall through — caller will see this as missing data later.
            pass

    def _pump_into_buffer(self) -> None:
        """Move all pending bytes from the slave into the internal buffer."""
        available = self._available()
        # 0xFFFF means "buffer not ready / nothing queued" (default slave
        # state before any AT command, or while the slave is still preparing
        # the next response). Treat that — and anything close to it — as 0.
        if available == 0 or available >= 0xFF00:
            return
        while 0 < available < 0xFF00:
            chunk = min(available, MAX_PL_LEN)
            self._buffer.extend(self._frame_read(chunk))
            if len(self._buffer) > READ_BUFFER_LIMIT:
                # Hard cap: drop oldest bytes to keep memory bounded.
                del self._buffer[: len(self._buffer) - READ_BUFFER_LIMIT]
            available -= chunk

    def _take_line(self) -> Optional[bytes]:
        idx = self._buffer.find(b"\n")
        if idx < 0:
            return None
        line = bytes(self._buffer[:idx]).rstrip(b"\r")
        del self._buffer[: idx + 1]
        return line if line else None

    def _available(self) -> int:
        self._bus.i2c_rdwr(
            i2c_msg.write(
                self._address,
                [FEATURE_TRANSPORT, CMD_AVAILABLE, 0x00, 0x00, 0x00, 0x00],
            )
        )
        time.sleep(WAIT_DELAY_S)
        rx = i2c_msg.read(self._address, 2)
        self._bus.i2c_rdwr(rx)
        data = bytes(rx)
        return (data[0] << 8) | data[1]

    def _frame_read(self, length: int) -> bytes:
        self._bus.i2c_rdwr(
            i2c_msg.write(
                self._address,
                [
                    FEATURE_TRANSPORT,
                    CMD_READ,
                    (length >> 8) & 0xFF,
                    length & 0xFF,
                    0x00,
                    0x00,
                ],
            )
        )
        time.sleep(WAIT_DELAY_S)
        rx = i2c_msg.read(self._address, length)
        self._bus.i2c_rdwr(rx)
        return bytes(rx)

    def _frame_write(self, payload: bytes) -> None:
        """Send up to MAX_PL_LEN bytes wrapped in a FEATURE_TRANSPORT CMD_WRITE."""
        view = memoryview(payload)
        offset = 0
        while offset < len(view):
            chunk = bytes(view[offset:offset + MAX_PL_LEN])
            header = [
                FEATURE_TRANSPORT,
                CMD_WRITE,
                (len(chunk) >> 8) & 0xFF,
                len(chunk) & 0xFF,
            ]
            trailer = [0x00, 0x00]  # checksum placeholder (Seeed lib also writes 0,0)
            self._bus.i2c_rdwr(
                i2c_msg.write(self._address, header + list(chunk) + trailer)
            )
            time.sleep(WAIT_DELAY_S)
            offset += MAX_PL_LEN


def _parse_payload(
    decoded: Any, class_name_lut: Dict[int, str]
) -> List[RawDetection]:
    """Extract detections from any of the SSCMA JSON shapes we have seen."""
    if not isinstance(decoded, dict):
        return []

    data = decoded.get("data")
    if isinstance(data, dict) and isinstance(data.get("boxes"), list):
        return _parse_box_list(data["boxes"], class_name_lut)
    if isinstance(decoded.get("boxes"), list):
        return _parse_box_list(decoded["boxes"], class_name_lut)
    if isinstance(decoded.get("detections"), list):
        return _parse_detection_dicts(decoded["detections"], class_name_lut)
    return []


def _parse_box_list(
    boxes: list, class_name_lut: Dict[int, str]
) -> List[RawDetection]:
    """SSCMA box: [center_x, center_y, w, h, score(0-100), target_id]."""
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
                class_name=str(
                    item.get("name") or class_name_lut.get(class_id, str(class_id))
                ),
                confidence=confidence,
                bbox_x=int(item.get("x", 0)),
                bbox_y=int(item.get("y", 0)),
                bbox_w=int(item.get("w", 0)),
                bbox_h=int(item.get("h", 0)),
            )
        )
    return result
