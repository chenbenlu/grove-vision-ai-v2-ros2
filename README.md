# 🚗 Control Lab — 自走小車視覺感知系統

本套件負責讀取 Grove Vision AI V2 模組的影像辨識結果，轉換成 ROS 2 訊息發布到 `/perception/road_signs`，供下游的自走小車決策系統訂閱使用。

---

## 🐳 1. Docker 環境啟動（建議首選）

不污染主機 Python / ROS 環境。`src/` bind-mount，改 code 不用 rebuild image。

### A. PC 開發（amd64，自動 fallback Mock）

PC 沒接 Grove V2，container 起來會 WARN 一句後自動切 Mock，持續發布虛擬路標：

```bash
cd ~/control_lab
docker compose up --build
```

### B. Pi 實機（arm64，接 Grove V2 USB-C）

```bash
export DIALOUT_GID=$(getent group dialout | cut -d: -f3)   # 通常 20
docker compose -f docker-compose.yml -f docker-compose.pi.yml up --build
```

> **第一次** `--build` 在 Pi 上要下載 arm64 base image（約 200 MB），需要等幾分鐘。之後改 code 直接 `docker compose restart vision-ai` 即可（entrypoint 內會自動重 `colcon build`）。

---

## 🚀 2. 執行與看結果

啟動之後 container 內就在發布訊息。從另一個 terminal 看：

```bash
# 進 container 直接 echo (簡單)
docker compose exec vision-ai bash -c \
  "source install/setup.bash && ros2 topic echo /perception/road_signs"

# 或在 host 上直接 echo（需要 host 已 source ROS 2 Humble + ROS_DOMAIN_ID 一致）
ros2 topic echo /perception/road_signs
```

### 強制跑 Mock 節點（不要 vision_ai_node 自動 fallback 路徑）

```bash
docker compose run --rm vision-ai \
  ros2 run vision_perception mock_vision_node
```

---

## 📥 3. 輸出訊息結構（開發核心！）

> **請特別注意**：你的控制節點要訂閱 **`/perception/road_signs`**，解析下面格式：

```
$ ros2 interface show vision_perception/msg/VisionAI
std_msgs/Header header
Detection[] detections
    uint8   class_id      # 類別索引 (對應 class_names)
    string  class_name    # 類別名稱 (e.g. "stop", "yield")
    float32 confidence    # 信心度 0.0 ~ 1.0
    uint16  bbox_x        # 左上角 x (pixel)
    uint16  bbox_y        # 左上角 y
    uint16  bbox_w        # 寬
    uint16  bbox_h        # 高
```

每幀一則 `VisionAI`，內含 0..N 個 `Detection`。QoS depth = 10。

---

## ⚙️ 4. 參數設定（可自行調整）

設定檔在 [`config/params.yaml`](src/vision_perception/config/params.yaml)，也可在 CLI 用 `--ros-args -p key:=value` 即時覆寫。

| Key | 預設 | 說明 |
|---|---|---|
| `serial_port` | `/dev/ttyACM0` | Grove V2 USB-C 插上 Pi 後的虛擬序列埠 |
| `baud_rate` | `921600` | Grove V2 出廠固定值 |
| **`confidence_threshold`** | **`0.6`** | **辨識靈敏度**：低於這個信心度的偵測不會 publish。調低 → 更敏感但易誤判，調高 → 更可靠但易漏 |
| `poll_rate_hz` | `20.0` | 讀取頻率（每秒幾次） |
| `fallback_to_mock` | `true` | Serial 開不起來時自動切 Mock |
| **`class_names`** | `[stop, yield, speed_30, speed_60]` | **類別對應表**：index 對應韌體回的 `class_id`。**部署時必須跟你的實際模型 label 順序對齊！** |

範例：暫時提高靈敏度測試：

```bash
docker compose run --rm vision-ai \
  ros2 run vision_perception vision_ai_node --ros-args -p confidence_threshold:=0.4
```

---

## 🛠️ 5. 常見除錯（Troubleshooting）

| 症狀 | 處理 |
|---|---|
| `Serial unavailable: could not open port /dev/ttyACM0` | Grove V2 沒接、線材沒支援資料（純供電線會中招），或裝置號被佔到 ttyACM1。`ls /dev/ttyACM*` 確認。 |
| `PermissionError: '/dev/ttyACM0'` | 沒在 `dialout` group → `sudo usermod -aG dialout $USER` 後**登出再登入**讓 group 生效。 |
| topic 收得到、但 `detections: []` 持續空 | 鏡頭前真的沒物體，或 `confidence_threshold` 設太高。試 `--ros-args -p confidence_threshold:=0.3` 看會不會冒出來。 |
| `class_name` 是純數字（`'1'`, `'2'`） | `class_names` 的 index 跟韌體實際 `class_id` 對不上，parser 退而顯示 id 字串。改 `params.yaml` 的 list 順序後 restart container。 |
| `topic echo` 報 `message type vision_perception/msg/VisionAI is invalid` | 該 terminal 沒 source `install/setup.bash`，或 host 沒 build 過套件。改用 container 內 echo：`docker compose exec vision-ai bash -c "source install/setup.bash && ros2 topic echo /perception/road_signs"` |
| Docker 跑、host 看不到 topic | 主機跟 compose 的 `ROS_DOMAIN_ID` 不同。檢查 `echo $ROS_DOMAIN_ID`，預設 `0`。 |
