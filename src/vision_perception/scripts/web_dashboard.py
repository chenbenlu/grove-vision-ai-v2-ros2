import serial
import json
import threading
from flask import Flask, render_template_string
from flask_socketio import SocketIO

# --- 參數設定 ---
SERIAL_PORT = '/dev/ttyACM0'
BAUD_RATE = 921600

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# 全域變數儲存最新資料
latest_vision_data = {"status": "waiting"}

# --- HTML 前端介面 ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>小車視覺戰情室</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'Inter', sans-serif;
            background: #0d1117;
            color: #e6edf3;
            min-height: 100vh;
            padding: 24px;
        }

        header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 28px;
            border-bottom: 1px solid #21262d;
            padding-bottom: 16px;
        }

        header h1 {
            font-size: 1.4em;
            font-weight: 700;
            color: #e6edf3;
        }

        #conn-badge {
            margin-left: auto;
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 0.78em;
            font-weight: 600;
            background: #21262d;
            color: #8b949e;
            transition: all 0.3s;
        }
        #conn-badge.connected { background: #0d4429; color: #3fb950; }
        #conn-badge.alert     { background: #3d1f00; color: #f78166; }

        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }

        @media (max-width: 700px) { .grid { grid-template-columns: 1fr; } }

        .card {
            background: #161b22;
            border: 1px solid #21262d;
            border-radius: 12px;
            padding: 20px;
        }

        .card h2 {
            font-size: 0.78em;
            font-weight: 600;
            color: #8b949e;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 14px;
        }

        /* Status card */
        #status-text {
            font-size: 2em;
            font-weight: 700;
            text-align: center;
            padding: 16px 0;
            transition: color 0.3s;
        }
        #status-text.ok   { color: #3fb950; }
        #status-text.stop { color: #f78166; }
        #status-text.wait { color: #8b949e; }

        /* Counter */
        #frame-count {
            text-align: center;
            font-size: 0.85em;
            color: #8b949e;
            margin-top: 6px;
        }

        /* Detected objects list */
        #detections-list {
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 8px;
            min-height: 60px;
        }

        #detections-list li {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #0d1117;
            border: 1px solid #21262d;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 0.88em;
        }

        #detections-list li .label  { font-weight: 600; color: #79c0ff; }
        #detections-list li .score  { color: #3fb950; font-family: 'JetBrains Mono', monospace; }
        #detections-list li .coords { color: #8b949e; font-size: 0.8em; font-family: 'JetBrains Mono', monospace; }

        /* Raw JSON */
        #raw-data {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8em;
            background: #0d1117;
            border: 1px solid #21262d;
            border-radius: 8px;
            padding: 14px;
            overflow-x: auto;
            max-height: 260px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-break: break-all;
            color: #a5d6ff;
            line-height: 1.5;
        }

        /* Timeline */
        #timeline {
            display: flex;
            flex-direction: column;
            gap: 6px;
            max-height: 260px;
            overflow-y: auto;
        }

        .timeline-entry {
            display: flex;
            gap: 10px;
            font-size: 0.8em;
            align-items: flex-start;
        }

        .timeline-entry .ts {
            color: #8b949e;
            font-family: 'JetBrains Mono', monospace;
            flex-shrink: 0;
        }

        .timeline-entry .msg { color: #e6edf3; }
        .timeline-entry .msg.raw { color: #f0883e; }

        /* Pulse dot */
        .pulse {
            display: inline-block;
            width: 8px; height: 8px;
            border-radius: 50%;
            background: #3fb950;
            margin-right: 6px;
            animation: pulse-anim 1.4s infinite;
        }

        @keyframes pulse-anim {
            0%   { opacity: 1; transform: scale(1); }
            50%  { opacity: 0.4; transform: scale(1.4); }
            100% { opacity: 1; transform: scale(1); }
        }
    </style>
</head>
<body>
    <header>
        <span>🚗</span>
        <h1>自走小車視覺戰情室</h1>
        <span id="conn-badge">● 等待連線</span>
    </header>

    <div class="grid">
        <!-- 狀態卡 -->
        <div class="card" style="grid-row: span 1;">
            <h2>🔎 偵測狀態</h2>
            <div id="status-text" class="wait">⏳ 等待資料...</div>
            <div id="frame-count">已接收 <span id="fc">0</span> 幀</div>
        </div>

        <!-- 偵測物件 -->
        <div class="card">
            <h2>📦 偵測到的物件</h2>
            <ul id="detections-list">
                <li style="color:#8b949e; justify-content:center;">尚未收到資料</li>
            </ul>
        </div>

        <!-- 原始 JSON -->
        <div class="card">
            <h2>🧾 原始 JSON 資料</h2>
            <div id="raw-data">等待中...</div>
        </div>

        <!-- 事件紀錄 -->
        <div class="card">
            <h2><span class="pulse"></span>即時事件紀錄</h2>
            <div id="timeline"></div>
        </div>
    </div>

    <script>
        var socket = io();
        var frameCount = 0;

        function now() {
            return new Date().toLocaleTimeString('zh-TW', { hour12: false });
        }

        function addTimeline(msg, isRaw) {
            var tl = document.getElementById('timeline');
            var entry = document.createElement('div');
            entry.className = 'timeline-entry';
            entry.innerHTML = '<span class="ts">' + now() + '</span>' +
                              '<span class="msg' + (isRaw ? ' raw' : '') + '">' + msg + '</span>';
            tl.prepend(entry);
            // 只保留最近 40 筆
            while (tl.children.length > 40) tl.removeChild(tl.lastChild);
        }

        socket.on('connect', function() {
            document.getElementById('conn-badge').textContent = '● WebSocket 已連線';
            document.getElementById('conn-badge').className = 'connected';
            addTimeline('WebSocket 連線成功', false);
        });

        socket.on('disconnect', function() {
            document.getElementById('conn-badge').textContent = '● 連線中斷';
            document.getElementById('conn-badge').className = 'alert';
            addTimeline('WebSocket 連線中斷', false);
        });

        socket.on('update_data', function(msg) {
            frameCount++;
            document.getElementById('fc').textContent = frameCount;

            // 原始 JSON
            document.getElementById('raw-data').textContent =
                typeof msg === 'string' ? msg : JSON.stringify(msg, null, 2);

            // 連線徽章
            var badge = document.getElementById('conn-badge');
            badge.textContent = '● Serial 接收中';
            badge.className = 'connected';

            // 如果是 raw string (非JSON)
            if (msg.__raw) {
                addTimeline('📦 ' + msg.__raw, true);
                document.getElementById('status-text').textContent = '📡 接收原始資料中...';
                document.getElementById('status-text').className = 'wait';
                document.getElementById('detections-list').innerHTML =
                    '<li style="color:#8b949e;justify-content:center;">等待有效 JSON 資料</li>';
                return;
            }

            // 解析偵測物件
            var list = document.getElementById('detections-list');
            list.innerHTML = '';

            // 支援常見格式: boxes / detections / results / objects 陣列
            var items = msg.boxes || msg.detections || msg.results || msg.objects || [];
            if (!Array.isArray(items) && typeof msg === 'object') {
                // 嘗試找第一個陣列欄位
                for (var k in msg) {
                    if (Array.isArray(msg[k]) && msg[k].length > 0) {
                        items = msg[k]; break;
                    }
                }
            }

            if (items.length > 0) {
                items.forEach(function(item) {
                    var li = document.createElement('li');
                    var label = item.label || item.class || item.name || item.type || JSON.stringify(item);
                    var score = item.score !== undefined ? (item.score * 100).toFixed(1) + '%' :
                                item.confidence !== undefined ? (item.confidence * 100).toFixed(1) + '%' : '';
                    var coords = '';
                    if (item.x !== undefined) coords = 'x:' + item.x + ' y:' + item.y;
                    else if (item.bbox) coords = JSON.stringify(item.bbox);

                    li.innerHTML = '<span class="label">' + label + '</span>' +
                                   (score  ? '<span class="score">'  + score  + '</span>' : '') +
                                   (coords ? '<span class="coords">' + coords + '</span>' : '');
                    list.appendChild(li);
                });
                addTimeline('偵測到 ' + items.length + ' 個物件', false);
            } else {
                list.innerHTML = '<li style="color:#8b949e;justify-content:center;">無偵測結果</li>';
                addTimeline('收到資料，無偵測結果', false);
            }

            // 狀態更新
            var statusEl = document.getElementById('status-text');
            var rawStr = JSON.stringify(msg).toLowerCase();
            if (rawStr.includes('stop')) {
                statusEl.textContent = '🛑 偵測到停止標誌！';
                statusEl.className = 'stop';
                addTimeline('⚠️ 偵測到 Stop 標誌', false);
            } else if (Object.keys(msg).length > 0) {
                statusEl.textContent = '✅ 行駛中 (無障礙物)';
                statusEl.className = 'ok';
            }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

def read_serial_data():
    """背景執行緒：讀取 Serial 並透過 Socket 推播給網頁"""
    global latest_vision_data
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"✅ 連線至 {SERIAL_PORT} (鮑率: {BAUD_RATE})")
        while True:
            # 直接 readline()，不用 in_waiting 判斷
            # USB CDC (/dev/ttyACM0) 的 in_waiting 在某些驅動下恆為 0
            raw_bytes = ser.readline()
            if not raw_bytes:
                continue  # timeout，無資料
            raw_data = raw_bytes.decode('utf-8', errors='replace').strip()
            if not raw_data:
                continue
            try:
                data = json.loads(raw_data)
                latest_vision_data = data
                socketio.emit('update_data', data)
            except json.JSONDecodeError:
                # 非 JSON 時也推播，讓前端能顯示原始資料
                print(f"📦 [原始資料]: {raw_data}")
                socketio.emit('update_data', {'__raw': raw_data})
    except Exception as e:
        print(f"Serial 錯誤: {e}")

if __name__ == '__main__':
    thread = threading.Thread(target=read_serial_data, daemon=True)
    thread.start()

    print("🌐 網頁伺服器啟動！請在瀏覽器輸入: http://127.0.0.1:5000")
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)