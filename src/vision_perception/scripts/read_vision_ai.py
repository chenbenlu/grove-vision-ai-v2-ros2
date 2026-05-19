import serial
import json
import time

# ==========================================
# 參數設定區 (請根據你的電腦修改 SERIAL_PORT)
# ==========================================
SERIAL_PORT = '/dev/ttyACM0'  # Windows 範例: 'COM3', Mac/Linux 範例: '/dev/ttyACM0'
BAUD_RATE = 921600    # Grove Vision AI V2 使用 921600 baud

def main():
    try:
        # 1. 建立 Serial 連線
        #    timeout=1 表示 readline() 最多等 1 秒後自動回傳（避免永久卡住）
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"✅ 成功連接到 {SERIAL_PORT} (鮑率: {BAUD_RATE})")
        print("等待接收 NPU 辨識結果...")
        print(f"   [診斷] in_waiting 初始值: {ser.in_waiting}")
        print("=" * 40)

        # 2. 持續監聽資料
        #    ⚠️  不使用 in_waiting 判斷：USB CDC 虛擬序列埠
        #       (如 /dev/ttyACM0) 的 in_waiting 在某些驅動下恆為 0，
        #       直接呼叫 readline() 才能正確阻塞等待資料。
        while True:
            # readline() 讀到 '\n' 或等到 timeout=1s 才回傳
            raw_bytes = ser.readline()

            if not raw_bytes:
                # timeout 到期，沒有資料 → 繼續等待
                print(".", end="", flush=True)
                continue

            # 有資料 → 嘗試 UTF-8 解碼
            raw_data = raw_bytes.decode('utf-8', errors='replace').strip()

            if not raw_data:
                continue

            # 3. 嘗試將資料解析為 JSON 格式 (提取座標與類別)
            try:
                data = json.loads(raw_data)
                print()  # 換行（沖掉前面的 '.' 診斷點）
                print("🎯 [辨識成功]")

                # 將 JSON 排版印出，方便你觀察結構
                print(json.dumps(data, indent=2, ensure_ascii=False))
                print("-" * 40)

                # === 你可以在這裡加入你的小車控制邏輯 ===
                # 例如:
                # if "classes" in data and "stop" in data["classes"]:
                #     print("看見 Stop 標誌，準備停車！")

            except json.JSONDecodeError:
                # 如果模組吐出的不是 JSON (例如開機時的 Debug log)，就當作普通字串印出
                print()
                print(f"📦 [原始資料 hex]: {raw_bytes.hex(' ')}")
                print(f"📦 [原始資料 str]: {raw_data}")

    except serial.SerialException as e:
        print(f"❌ 無法開啟通訊埠 {SERIAL_PORT}。")
        print("請檢查: 1. 線材是否支援資料傳輸  2. 埠號是否正確  3. 模組是否被其他程式(如 Arduino IDE)佔用")
        print(f"詳細錯誤: {e}")
    except KeyboardInterrupt:
        print("\n🛑 收到中斷指令，終止接收")
    finally:
        # 確保程式結束時安全關閉通訊埠
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("🔌 通訊埠已安全關閉")

if __name__ == '__main__':
    main()