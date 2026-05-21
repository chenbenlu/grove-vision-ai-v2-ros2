# Grove Vision AI V2 — ROS 2 Perception Package

![ROS 2 Humble](https://img.shields.io/badge/ROS%202-Humble-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-amd64%20%7C%20arm64-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

ROS 2 (Humble) 套件：將 Grove Vision AI V2 (Himax WE2 + SenseCraft AI) 的 SSCMA 偵測結果以 `vision_perception/msg/VisionAI` 發布。支援 **USB CDC**、**UART pins**、**I2C** 三種 transport，透過 `transport` 參數切換。

---

## Overview

推論工作完全交由 Grove Vision AI V2 模組內建 NPU 執行，主控端 (Raspberry Pi) 僅負責讀取、JSON 解析、信心度過濾與 ROS 2 訊息發布，不佔用主機 CPU。

| 項目 | 規格 |
|---|---|
| 感測器 | Grove Vision AI V2 (Himax WE2 NPU、SenseCraft AI 韌體) |
| Transport | USB CDC `/dev/ttyACM0` (預設) / UART `/dev/ttyAMA0` / I2C `/dev/i2c-1` @ `0x62` |
| 主控端 | Raspberry Pi 4 (Ubuntu 20.04 arm64) 或 x86_64 開發主機 |
| ROS 2 / 授權 | Humble / MIT |

---

## Prerequisites

| 元件 | 版本 |
|---|---|
| Docker Engine + Compose v2 | 20.10+ |
| 作業系統 | Ubuntu 20.04 / 22.04 |
| 硬體 (實機) | Raspberry Pi 4 + Grove Vision AI V2 |

Pi 端一次性設定（`get.docker.com` 一鍵腳本在 Ubuntu 20.04/Focal 會卡在 `docker-model-plugin`，故走官方 apt repo 手動步驟）：

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg i2c-tools
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker,dialout,i2c "$USER"   # 重新登入或 newgrp 生效
```

依實際接線方式修改 `/boot/firmware/config.txt`：

| 接線 | 需追加 |
|---|---|
| I2C | `dtparam=i2c_arm=on` |
| UART pins | `dtoverlay=disable-bt` |

走 UART pins 路徑時，另需從 `/boot/firmware/cmdline.txt` 移除 `console=serial0,115200`，避免 kernel console 佔用 `/dev/ttyAMA0`。修改後 `sudo reboot` 生效。

---

## Quick Start

```bash
git clone https://github.com/chenbenlu/grove-vision-ai-v2-ros2.git
cd grove-vision-ai-v2-ros2
```

### PC (x86_64)

僅供建置與程式碼驗證；無實體裝置會在啟動時直接結束。

```bash
docker compose build
```

### Pi 實機部署

依接線方式選擇 overlay，並對應設定 `params.yaml` 中的 `transport` / `serial_port`：

| 接線 | overlay | 額外參數 |
|---|---|---|
| USB-C → Pi USB-A | `docker-compose.pi-usb.yml` | — (預設) |
| GPIO 14/15 TX/RX | `docker-compose.pi-uart.yml` | `serial_port: /dev/ttyAMA0` |
| Grove 4-pin SDA/SCL | `docker-compose.pi-i2c.yml` | `transport: i2c` |

```bash
# USB CDC (預設)
export DIALOUT_GID=$(getent group dialout | cut -d: -f3)
docker compose -f docker-compose.yml -f docker-compose.pi-usb.yml up --build

# I2C
export I2C_GID=$(getent group i2c | cut -d: -f3)
docker compose -f docker-compose.yml -f docker-compose.pi-i2c.yml up --build
```

> 首次於 Pi 上 build 需下載 `linux/arm64` 基底映像 (~200 MB)。後續改 source 後執行 `docker compose restart vision-ai`，entrypoint 會自動增量 `colcon build`。

另開終端訂閱：

```bash
docker compose exec vision-ai \
  bash -c "source install/setup.bash && ros2 topic echo /vision/detections"
```

---

## Node API

執行：`ros2 run vision_perception vision_ai_node`

**Topic**：`/vision/detections` (`vision_perception/msg/VisionAI`, RELIABLE, depth = 10)

### Parameters

可透過 [`config/params.yaml`](src/vision_perception/config/params.yaml) 或 `--ros-args -p key:=value` 覆寫。

| 參數 | 型別 | 預設值 | 說明 |
|---|---|---|---|
| `transport` | string | `serial` | `serial` (USB CDC / UART pins) 或 `i2c` |
| `serial_port` | string | `/dev/ttyACM0` | `transport=serial` 時使用；UART pins 改 `/dev/ttyAMA0` |
| `baud_rate` | int | `921600` | |
| `i2c_bus` / `i2c_address` | int / int | `1` / `0x62` | `transport=i2c` 時使用 |
| `topic` | string | `/vision/detections` | |
| `frame_id` | string | `vision_ai` | `header.frame_id` |
| `confidence_threshold` | float | `0.6` | 低於此值不予發布 |
| `poll_rate_hz` | float | `20.0` | 讀取迴圈頻率 |
| `class_names` | string[] | `[stop, yield, speed_30, speed_60]` | index 對應韌體 `target_id` |

### Message Schema

```
# vision_perception/msg/VisionAI
std_msgs/Header header
Detection[]     detections

# vision_perception/msg/Detection
uint8   class_id
string  class_name
float32 confidence
uint16  bbox_x, bbox_y, bbox_w, bbox_h
```

---

## Troubleshooting

| 症狀 | 解決方式 |
|---|---|
| `Serial unavailable: could not open port /dev/ttyACM0` | `ls /dev/ttyACM*` 確認；換具資料訊號之線材；或將使用者加入 `dialout` 群組 |
| `I2C unavailable: no slave at 0x62` | `i2cdetect -y 1` 確認 0x62 ACK；若空白，power-cycle V2 |
| `I2C unavailable: cannot open I2C bus 1` | `/boot/firmware/config.txt` 缺 `dtparam=i2c_arm=on`，或使用者不在 `i2c` 群組 |
| `detections: []` 持續為空 | 鏡頭視野無目標、或 `confidence_threshold` 過高；I2C 初始化期 CMD_AVAILABLE 回 `0xFFFF` 屬正常 |
| `class_name` 為純數字 (`'1'`) | `class_names` 順序與部署模型不符 — 對齊後重啟 |
| `topic echo` 回傳 `message type ... is invalid` | 訂閱端未 `source install/setup.bash`；或改由容器內 `docker compose exec` |
| 主機端找不到容器內 Topic | 兩端 `ROS_DOMAIN_ID` 不一致 (預設 `0`) |

---

## Repository Layout

```
.
├── docker/                       # Dockerfile + entrypoint
├── docker-compose.yml            # 基底 (PC，無 device passthrough)
├── docker-compose.pi-usb.yml     # passthrough ttyACM0
├── docker-compose.pi-uart.yml    # passthrough ttyAMA0
├── docker-compose.pi-i2c.yml     # passthrough i2c-1
└── src/vision_perception/
    ├── msg/{Detection,VisionAI}.msg
    ├── launch/vision_perception.launch.py
    ├── config/params.yaml
    └── vision_perception_nodes/  # Python 模組 (避開 msg namespace)
        ├── vision_ai_node.py
        ├── serial_reader.py      # USB CDC / UART pins
        ├── i2c_reader.py         # SSCMA-Micro FEATURE_TRANSPORT
        └── _types.py
```

---

## License

MIT — 詳見 [LICENSE](LICENSE)。
