# Track B — Smart Agriculture — Data/Backend

Vai: **Data/Backend** (MQTT → buffer → Tool/API → WebSocket). Đã test chạy được, xong sẵn để cả đội cắm vào ngay từ tối nay.

## Chạy thử (không cần broker MQTT thật)

```bash
pip install -r requirements.txt --break-system-packages
uvicorn app.main:app --reload --port 8000
```

Mặc định `SIMULATE=true` — server tự phát dữ liệu giả cho cả 6 thiết bị mỗi 3 giây, để bạn AI/ML và Frontend code song song ngay, không phải chờ bạn có broker thật.

Xem docs tự sinh tại `http://localhost:8000/docs`.

## Khi có broker thật của BTC

1. Copy `.env.example` → `.env`, điền `MQTT_BROKER_HOST`, `MQTT_BROKER_PORT`, `MQTT_USERNAME/PASSWORD`, `MQTT_TEST_TOPIC` (broker thật đội mình đang dùng chạy sau Cloudflare cổng 443 → cần `MQTT_TRANSPORT=websockets`, `MQTT_USE_TLS=true`, `MQTT_WS_PATH=/mqtt` — đã xác nhận qua MQTTX + `paho-mqtt` thật).
2. Payload thật của BTC là **1 message chứa cả 6 thiết bị** (`{"devices": [{"deviceCode": "SOIL_01", "metrics": {...}}, ...]}`), không phải 1 message/1 thiết bị như giả định ban đầu — `parse_payload()` trong `app/mqtt_client.py` đã được viết lại theo đúng schema này, có fallback cho schema phẳng cũ nếu BTC đổi lại.
3. Chạy **chỉ 1 lệnh**:
   ```bash
   SIMULATE=false uvicorn app.main:app --port 8000
   ```
   MQTT client thật chạy trong background thread của CHÍNH process này (`on_startup` trong `main.py`) — **không chạy `python -m app.mqtt_client` như 1 tiến trình riêng**, vì `farm_state` là biến RAM trong 1 process, chạy tách rời sẽ không bao giờ chia sẻ được dữ liệu với server (bug đã gặp và sửa lúc test broker thật).

## Cho bạn AI/ML (Irrigation Planning / Resource Agent)

Đọc dữ liệu + rolling stats (mean/std/slope theo giờ, sliding window 300s):
```
GET /api/devices                 -> snapshot tất cả 6 thiết bị
GET /api/devices/{code}          -> 1 thiết bị
GET /api/devices/{code}/history  -> lịch sử thô để tự tính toán thêm (IsolationForest, forecast...)
GET /api/status                  -> danh sách thiết bị đang "sống" vs "stale" (kịch bản 3)
```

Sau khi Agent quyết định xong (thời điểm tưới, mức ưu tiên...), gọi Tool/API để **thực thi**:
```
POST /api/irrigation/plan   -> tạo kế hoạch tưới (có guardrail cứng chặn nếu bồn cạn / pH sai)
POST /api/tasks             -> tạo nhiệm vụ kiểm tra hiện trường
POST /api/notifications     -> gửi thông báo
GET  /api/report            -> báo cáo tổng hợp, tự động loại trừ thiết bị stale (không bịa số liệu)
```
Guardrail (`app/tools.py::check_irrigation_guardrail`) trả `403 Forbidden` kèm lý do nếu vi phạm — dùng đúng câu chữ "VETO: ..." khi demo pitch, khớp với gợi ý trong file context.

## Cho bạn Frontend

```
WS /ws/telemetry
```
Kết nối 1 lần, nhận snapshot ngay lúc connect, sau đó server tự đẩy `{"event": "snapshot", "data": {...}}` mỗi 3s, cộng thêm event `plan_created` / `task_created` / `notification` / `telemetry` mỗi khi có hành động mới — đủ để dashboard update realtime không cần polling.

Nút bắt buộc cho pitch — "bơm dữ liệu bất thường":
```
POST /api/simulate/inject?device_code=SOIL_01   body: {"soil_moisture": 3.0}
POST /api/simulate/freeze/{device_code}          -> giả lập cảm biến chết (demo kịch bản 3)
```

## Cho bạn LLM + Pitch

Toàn bộ 5 kịch bản trong đề (lập kế hoạch tưới, kiểm tra phiên tưới, dữ liệu gián đoạn) map thẳng vào các endpoint trên — không cần thêm tầng trung gian, LLM chỉ cần gọi các hàm trong `app/tools.py` qua function calling (mô tả tool bằng chính docstring có sẵn).

## Kiểm tra nhanh điều kiện chấp nhận Track B

| Điều kiện | Đã có |
|---|---|
| ≥4/6 thiết bị có dữ liệu | `GET /api/status` |
| ≥3 Agent, 1 tác vụ cần ≥2 Agent | scaffold sẵn chỗ cắm (IoT Agent đọc, Planning/Resource Agent quyết định, Action Agent gọi Tool/API) |
| ≥1 kế hoạch dùng dữ liệu MQTT | `data_snapshot` trong mỗi plan/task lưu đúng số liệu đã dùng |
| Tool/API tạo lịch tưới/nhiệm vụ/thông báo | có cả 3 |
| Verification sau hành động | `GET /api/irrigation/plan/{id}`, assert trong `tools.py` |
| Không vỡ layout mobile | phần Frontend tự làm — API đã CORS mở sẵn |

## Việc CHƯA làm (đúng nghĩa "để dành" cho bạn AI/ML)

- Isolation Forest / GradientBoostingRegressor cho anomaly + forecast — chưa đụng vào, dữ liệu sẵn ở `GET /api/devices/{code}/history` để bạn train.
- Gọi LLM (Gemini) cho tầng chẩn đoán — chỉ nên gọi khi có anomaly, kèm cooldown ~60s, đừng gọi mỗi điểm dữ liệu (cháy quota).
