# Grove Vision AI V2 — ROS 2 Perception Package

<!-- 徽章區（CI / 版本 / 授權 等可日後補上） -->
![ROS 2 Humble](https://img.shields.io/badge/ROS%202-Humble-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-amd64%20%7C%20arm64-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

ROS 2 (Humble) 套件，將 Grove Vision AI V2 (Himax WE2 + SenseCraft AI 韌體) 取得的 SSCMA 偵測結果，解析後以 `vision_perception/msg/VisionAI` 訊息發布於 `/perception/road_signs`。支援 **USB CDC (預設)** 與 **I2C** 兩種 transport，透過 `transport` 參數切換。

---

## Overview

本套件設計為自走小車決策層的視覺輸入。推論工作完全交由 Grove Vision AI V2 模組內建 NPU 執行，主控端 (Raspberry Pi) 僅負責串列讀取、JSON 解析、信心度過濾與 ROS 2 訊息發布，不佔用主機 CPU 進行影像運算。

| 項目 | 規格 |
|---|---|
| 感測器 | Grove Vision AI V2 (Himax WE2 NPU、SenseCraft AI 韌體) |
| 傳輸介面 | **USB CDC** (`/dev/ttyACM0` @ 921600, 預設) 或 **I2C** (`/dev/i2c-1`, addr `0x62`, 400 kHz, SSCMA-Micro `FEATURE_TRANSPORT` framed；需 firmware 支援) |
| 主控端 | Raspberry Pi 4 (Ubuntu 20.04 arm64) 或 x86_64 開發主機 |
| ROS 2 版本 | Humble |
| 授權 | MIT |

---

## Features

- **硬體與模擬模式介面對等**：`vision_ai_node` 連接實體模組；`mock_vision_node` 提供模擬資料供下游節點整合測試。
- **失效自動降級**：偵測串列裝置不可用時自動切換為模擬資料來源，行為由 `fallback_to_mock` 參數控制。
- **雙 transport 可切換**：USB CDC (PySerial @ 921600) 或 I2C (SSCMA-Micro `FEATURE_TRANSPORT` framed)，由 `transport` 參數選擇。
- **SSCMA 開機握手程序**：USB CDC 路徑開啟 port 時關閉 DTR/RTS 防 Himax WE2 reset；等待 `is_ready` 後送出 `AT+INVOKE=-1,0,1\r` 啟動連續推論並抑制 base64 影像欄位 (~10× 頻寬節省)。
- **多種 JSON Schema 容錯**：支援 SSCMA 標準 `data.boxes`、簡化型 `boxes`、舊版 `detections` 三種格式。
- **日誌節流**：僅於類別集合變化或連續低信心度達門檻時輸出，避免高速迴圈洗版。
- **多架構容器映像**：單一 Dockerfile 同時支援 `linux/amd64` (PC) 與 `linux/arm64` (Pi)；實機部署透過 compose overlay 注入硬體裝置。

---

## Prerequisites

| 元件 | 版本 | 備註 |
|---|---|---|
| Docker Engine | 20.10+ | 必要 |
| Docker Compose | v2+ | 隨新版 Docker 提供 |
| 作業系統 | Ubuntu 20.04 / 22.04 | 已測試 |
| 硬體 (實機部署) | Raspberry Pi 4 + Grove Vision AI V2 (USB-C 或 Grove 4-pin) | PC 開發可省略 |

Pi 端一次性設定 (首次部署執行)：

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo apt-get install -y i2c-tools
sudo usermod -aG docker,dialout,i2c "$USER"
# 重新登入或 `newgrp dialout` 以使群組生效
# I2C 路徑另需 /boot/firmware/config.txt 含 `dtparam=i2c_arm=on`
```

---

## Quick Start

### 1. 取得專案

```bash
git clone https://github.com/chenbenlu/grove-vision-ai-v2-ros2.git
cd grove-vision-ai-v2-ros2
```

### 2. 開發環境 (PC, x86_64, 自動 fallback Mock)

```bash
docker compose up --build
```

另開終端查看訊息：

```bash
docker compose exec vision-ai \
  bash -c "source install/setup.bash && ros2 topic echo /perception/road_signs"
```

### 3. 實機部署 (Raspberry Pi + Grove Vision AI V2)

**USB CDC 路徑 (預設，相容所有 V2 firmware build)**：

```bash
export DIALOUT_GID=$(getent group dialout | cut -d: -f3)   # 通常 20
docker compose -f docker-compose.yml -f docker-compose.pi.yml up --build
```

**I2C 路徑 (需 firmware 支援 SSCMA-Micro `FEATURE_TRANSPORT`)**：

```bash
export I2C_GID=$(getent group i2c | cut -d: -f3)
docker compose -f docker-compose.yml -f docker-compose.pi-i2c.yml up --build
```

> 首次於 Pi 上 build 需下載 `linux/arm64` 基底映像 (約 200 MB)。後續修改 source 後執行 `docker compose restart vision-ai`，entrypoint 會自動進行增量 `colcon build`。  
> 並非所有 V2 firmware 都支援 I2C；2023 年中之前的 SenseCraft AI build 沒有 `AT+DFTTPT` 與 I2C transport server，I2C 上會看到 0x62 ACK 但 FEATURE_TRANSPORT 框架請求無回應。若 I2C 路徑啟動後讀不到資料，請改回 USB CDC 或升級 firmware (SenseCraft Studio)。

---

## Node API

### Nodes

| 節點 | 執行指令 | 角色 |
|---|---|---|
| `vision_ai_node` | `ros2 run vision_perception vision_ai_node` | 實機讀取節點；串列裝置不可用時自動降級為 Mock |
| `mock_vision_node` | `ros2 run vision_perception mock_vision_node` | 模擬資料節點，供下游節點開發與整合測試 |

### Published Topics

| Topic | Type | QoS | 說明 |
|---|---|---|---|
| `/perception/road_signs` | `vision_perception/msg/VisionAI` | RELIABLE, depth = 10 | 每幀一則訊息，內含 0..N 筆 `Detection` |

### Subscribed Topics

無。

### Parameters

預設值由節點程式碼宣告，可透過 [`config/params.yaml`](src/vision_perception/config/params.yaml) 或 `--ros-args -p key:=value` 覆寫。

| 參數 | 型別 | 預設值 | 說明 |
|---|---|---|---|
| `transport` | string | `serial` | Transport 選擇：`serial` (USB CDC) 或 `i2c` |
| `serial_port` | string | `/dev/ttyACM0` | `transport=serial` 時使用 |
| `baud_rate` | int | `921600` | USB CDC 速率 |
| `i2c_bus` | int | `1` | `transport=i2c` 時使用；Pi 4 預設 `1` (`/dev/i2c-1`) |
| `i2c_address` | int | `0x62` | I2C slave 位址 (Grove V2 出廠固定) |
| `confidence_threshold` | float | `0.6` | 偵測信心度門檻；低於此值不予發布 |
| `poll_rate_hz` | float | `20.0` | 讀取迴圈頻率 (Hz) |
| `fallback_to_mock` | bool | `true` | 串列開啟或初始化失敗時自動切換為 Mock |
| `class_names` | string[] | `[stop, yield, speed_30, speed_60]` | 類別索引對應表；index 即為韌體回傳之 `target_id` |

### Message Schema

```
# vision_perception/msg/VisionAI
std_msgs/Header header
Detection[]     detections

# vision_perception/msg/Detection
uint8   class_id        # 類別索引
string  class_name      # 類別名稱 (由 class_names 參數對應)
float32 confidence      # 信心度 [0.0, 1.0]
uint16  bbox_x          # bounding box 左上角 x (pixel)
uint16  bbox_y          # bounding box 左上角 y (pixel)
uint16  bbox_w          # 寬度
uint16  bbox_h          # 高度
```

---

## Troubleshooting

| 症狀 | 可能原因 | 解決方式 |
|---|---|---|
| `Serial unavailable: could not open port /dev/ttyACM0` | USB-C 未接、線材無資料線、裝置號跳到 `ttyACM1` | `ls /dev/ttyACM*` 確認；換具資料訊號之線材 |
| `PermissionError: '/dev/ttyACM0'` | 使用者不在 `dialout` 群組 | `sudo usermod -aG dialout $USER` 後重新登入 |
| I2C 路徑 topic 收得到、`detections: []` 持續為空 | Firmware 沒有 SSCMA-Micro I2C transport server (典型於 2023 年中前 SenseCraft AI build) | 改用 `transport=serial` (USB CDC)，或於 SenseCraft Studio 重 flash 較新 firmware |
| `I2C unavailable: no slave at 0x62 on bus 1` | Grove V2 未供電 / Grove 線未連接 / bus 鎖死 | `i2cdetect -y 1` 確認 0x62 ACK；若空白，請 power-cycle V2 |
| `I2C unavailable: cannot open I2C bus 1` | I2C-1 未啟用，或使用者不在 `i2c` 群組 | 確認 `/boot/firmware/config.txt` 含 `dtparam=i2c_arm=on`；`sudo usermod -aG i2c $USER` 後重新登入 |
| Topic 有訊息但 `detections: []` 持續為空 | 鏡頭視野無目標物件，或 `confidence_threshold` 設定過高 | 暫時降低門檻：`--ros-args -p confidence_threshold:=0.3` |
| `class_name` 為純數字字串 (`'1'`、`'2'`) | `class_names` 索引未對應實際部署模型之 label 順序 | 調整 `params.yaml` 內 `class_names` 順序後重啟容器 |
| `topic echo` 回傳 `message type ... is invalid` | 訂閱端執行環境缺少訊息型別定義 | 於該終端執行 `source install/setup.bash`；或改由容器內部使用 `docker compose exec ...` |
| 主機端無法發現容器內 Topic | 主機與 compose 服務之 `ROS_DOMAIN_ID` 不一致 | 確保兩端 `ROS_DOMAIN_ID` 相同 (預設 `0`) |

---

## Repository Layout

```
.
├── docker/
│   ├── Dockerfile              # ros:humble-ros-base + pyserial + colcon
│   └── entrypoint.sh           # source ROS env → colcon build → exec CMD
├── docker-compose.yml          # 基底 (PC，無 device passthrough)
├── docker-compose.pi.yml       # Pi USB CDC 覆寫 (/dev/ttyACM0 + dialout)
├── docker-compose.pi-i2c.yml   # Pi I2C 覆寫 (/dev/i2c-1 + i2c, transport=i2c)
└── src/vision_perception/
    ├── CMakeLists.txt          # hybrid ament_cmake (rosidl + Python)
    ├── package.xml
    ├── msg/{Detection,VisionAI}.msg
    ├── launch/vision_perception.launch.py
    ├── config/params.yaml
    ├── vision_perception_nodes/    # Python module (避開 msg namespace)
    │   ├── vision_ai_node.py
    │   ├── mock_vision_node.py
    │   ├── serial_reader.py        # USB CDC reader (SSCMA JSON over USART)
    │   ├── i2c_reader.py           # I2C reader (SSCMA-Micro FEATURE_TRANSPORT)
    │   ├── _mock_source.py
    │   └── _types.py
    └── test/test_mock_node.py
```

---

## License

本套件以 MIT License 釋出，詳見 [LICENSE](LICENSE)。
