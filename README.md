# Grove Vision AI V2 — ROS 2 Perception Package

<!-- 徽章區（CI / 版本 / 授權 等可日後補上） -->
![ROS 2 Humble](https://img.shields.io/badge/ROS%202-Humble-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-amd64%20%7C%20arm64-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

ROS 2 (Humble) 套件，將 Grove Vision AI V2 (Himax WE2 + SenseCraft AI 韌體) 取得的 SSCMA 偵測結果，解析後以 `vision_perception/msg/VisionAI` 訊息發布於 `/vision/detections`。支援 **USB CDC (預設)** 與 **I2C** 兩種 transport，透過 `transport` 參數切換；topic 與 frame_id 亦可在執行時覆寫。

---

## Overview

本套件設計為自走小車決策層的視覺輸入。推論工作完全交由 Grove Vision AI V2 模組內建 NPU 執行，主控端 (Raspberry Pi) 僅負責串列讀取、JSON 解析、信心度過濾與 ROS 2 訊息發布，不佔用主機 CPU 進行影像運算。

| 項目 | 規格 |
|---|---|
| 感測器 | Grove Vision AI V2 (Himax WE2 NPU、SenseCraft AI 韌體) |
| 傳輸介面 | **USB CDC** (`/dev/ttyACM0` @ 921600, 預設)、**UART pins** (`/dev/ttyAMA0` @ 921600, 需 `dtoverlay=disable-bt`)，或 **I2C** (`/dev/i2c-1`, addr `0x62`, 400 kHz, SSCMA-Micro `FEATURE_TRANSPORT` framed)。Serial 與 UART 共用同一個 `SerialVisionReader` |
| 主控端 | Raspberry Pi 4 (Ubuntu 20.04 arm64) 或 x86_64 開發主機 |
| ROS 2 版本 | Humble |
| 授權 | MIT |

---

## Features

- **即時視覺偵測**：`vision_ai_node` 連接實體 Grove Vision AI V2 模組，讀取 SSCMA JSON 偵測結果並發布 ROS 2 訊息。
- **三種 transport 可切換**：USB CDC、UART pins (PL011 GPIO 14/15)，或 I2C (SSCMA-Micro `FEATURE_TRANSPORT` framed)。前兩者共用 `SerialVisionReader`，僅切換 `serial_port`；第三者由 `transport=i2c` 啟動 `GroveVisionI2CReader`。三種均通過實機驗證。
- **SSCMA 開機握手程序**：兩種 reader 皆會 drain bootloader 噪音直到 `is_ready`，再送出 `AT+INVOKE=-1,0,1\r` 啟動連續推論並抑制 base64 影像欄位 (~10× 頻寬節省)。USB CDC 額外關閉 DTR/RTS 防 Himax WE2 reset。
- **多種 JSON Schema 容錯**：支援 SSCMA 標準 `data.boxes`、簡化型 `boxes`、舊版 `detections` 三種格式。
- **日誌節流**：僅於類別集合變化或連續低信心度達門檻時輸出，避免高速迴圈洗版。
- **可重定向發布**：`topic` 與 `frame_id` 皆為節點參數，便於整合至既有 TF 樹與 namespace。
- **多架構容器映像**：單一 Dockerfile 同時支援 `linux/amd64` (PC) 與 `linux/arm64` (Pi)；Pi compose overlay 同時 passthrough USB CDC 與 I2C 裝置，靠 `transport` 參數選擇實際使用的路徑。

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

### 2. 開發環境 (PC, x86_64)

PC 端需將 Grove V2 USB-C 接到 PC USB-A，以提供 `/dev/ttyACM0`。節點不再具備 mock fallback，無實體裝置會在啟動時直接結束。

```bash
docker compose up --build
```

另開終端查看訊息：

```bash
docker compose exec vision-ai \
  bash -c "source install/setup.bash && ros2 topic echo /vision/detections"
```

### 3. 實機部署 (Raspberry Pi + Grove Vision AI V2)

單一 Pi overlay 同時 passthrough `/dev/ttyACM0` 與 `/dev/i2c-1`；`transport` 預設為 `serial`，欲使用 I2C 請於 `config/params.yaml` 改為 `i2c` 或加上 `--ros-args -p transport:=i2c`。

```bash
export DIALOUT_GID=$(getent group dialout | cut -d: -f3)   # 通常 20
export I2C_GID=$(getent group i2c | cut -d: -f3)           # 通常 998
docker compose -f docker-compose.yml -f docker-compose.pi.yml up --build
```

> 首次於 Pi 上 build 需下載 `linux/arm64` 基底映像 (約 200 MB)。後續修改 source 後執行 `docker compose restart vision-ai`，entrypoint 會自動進行增量 `colcon build`。

---

## Node API

### Nodes

| 節點 | 執行指令 | 角色 |
|---|---|---|
| `vision_ai_node` | `ros2 run vision_perception vision_ai_node` | 實機讀取節點 |

### Published Topics

| Topic | Type | QoS | 說明 |
|---|---|---|---|
| `/vision/detections` | `vision_perception/msg/VisionAI` | RELIABLE, depth = 10 | 每幀一則訊息，內含 0..N 筆 `Detection`（topic 名稱可由參數覆寫） |

### Subscribed Topics

無。

### Parameters

預設值由節點程式碼宣告，可透過 [`config/params.yaml`](src/vision_perception/config/params.yaml) 或 `--ros-args -p key:=value` 覆寫。

| 參數 | 型別 | 預設值 | 說明 |
|---|---|---|---|
| `transport` | string | `serial` | Transport 選擇：`serial` (USB CDC) 或 `i2c` |
| `serial_port` | string | `/dev/ttyACM0` | `transport=serial` 時使用；可改 `/dev/ttyAMA0` 走 PL011 UART pins (需 `dtoverlay=disable-bt`) |
| `baud_rate` | int | `921600` | USB CDC 與 UART pins 同速率 |
| `i2c_bus` | int | `1` | `transport=i2c` 時使用；Pi 4 預設 `1` (`/dev/i2c-1`) |
| `i2c_address` | int | `0x62` | I2C slave 位址 (Grove V2 出廠固定) |
| `topic` | string | `/vision/detections` | 發布的 topic 名稱 |
| `frame_id` | string | `vision_ai` | `header.frame_id`，用於 TF 座標系對應 |
| `confidence_threshold` | float | `0.6` | 偵測信心度門檻；低於此值不予發布 |
| `poll_rate_hz` | float | `20.0` | 讀取迴圈頻率 (Hz) |
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
| I2C 路徑 topic `detections: []` 持續為空 | Firmware I2C transport buffer 未就緒 (CMD_AVAILABLE 回 `0xFFFF`)，通常於初始化期間 | reader 已內建 0xFFFF 視為「尚未就緒」處理；如長時間持續為空請改用 `transport=serial` 比對，或對鏡頭放實際模型 label 對應之物件 |
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
├── docker-compose.pi.yml       # Pi 覆寫 (同時 passthrough /dev/ttyACM0 + /dev/i2c-1)
└── src/vision_perception/
    ├── CMakeLists.txt          # hybrid ament_cmake (rosidl + Python)
    ├── package.xml
    ├── msg/{Detection,VisionAI}.msg
    ├── launch/vision_perception.launch.py
    ├── config/params.yaml
    ├── vision_perception_nodes/    # Python module (避開 msg namespace)
    │   ├── vision_ai_node.py
    │   ├── serial_reader.py        # USB CDC reader (SSCMA JSON over USART)
    │   ├── i2c_reader.py           # I2C reader (SSCMA-Micro FEATURE_TRANSPORT)
    │   └── _types.py
    └── test/
```

---

## License

本套件以 MIT License 釋出，詳見 [LICENSE](LICENSE)。
