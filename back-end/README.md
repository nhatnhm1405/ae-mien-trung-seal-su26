# Backend — Smart Agriculture (Track B)

Một process duy nhất: MQTT ingest → windowing → anomaly detection → multi-agent LLM → WebSocket.

## Chạy

```bash
cd back-end
pip install -r requirements.txt

# Bắt buộc lần đầu — không có model thì pipeline không phát hiện được gì
python -m app.ml.train_anomaly_model
python -m app.ml.train_irrigation_model

uvicorn app.main:app --port 8000                    # dev: dữ liệu giả lập
SIMULATE=false uvicorn app.main:app --port 8000     # thi thật: broker BTC
```

Swagger đầy đủ: <http://localhost:8000/docs>

Cấu hình nằm trong `.env` (copy từ `.env.example`). `app/config.py` là nơi duy nhất
đọc nó — đừng hardcode host/topic ở chỗ khác.

| Biến | Tác dụng |
|---|---|
| `SIMULATE=false` | Dùng broker BTC thật thay vì simulator nội bộ |
| `AGENT_ON_ANOMALY=false` | Tắt tầng LLM, vẫn giữ anomaly detection — dùng khi hết quota hoặc mất mạng |
| `AGENT_COOLDOWN_SECONDS` | Giây tối thiểu giữa 2 lần gọi LLM cho **cùng** một thiết bị (mặc định 60) |

## Luồng dữ liệu

```
broker BTC (wss:443, hackathon/ae_mien_trung/#)
      │
      ▼
app/mqtt_client.py ── dispatch_reading() ──┐   ← simulator và nút inject cũng vào đây
                                            ▼
                                    app/pipeline.py
                                            │
      ┌─────────────────────────────────────┼──────────────────────────────┐
      ▼ mọi điểm dữ liệu                    ▼ chỉ khi bất thường            ▼
 farm_state.ingest()              app/ml/predict_anomaly()      app/agents/coordinator
 (deque + rolling 300s)             (<1ms, chạy luôn)           (1-3s, có cooldown 60s,
      │                                     │                     chạy thread riêng)
      └─────────────────┬───────────────────┴──────────────────────────────┘
                        ▼
              app/events.py → /ws/telemetry
```

Hai nguyên tắc: phát hiện bất thường **rẻ** nên chạy trên mọi điểm dữ liệu; LLM **đắt**
nên chỉ chạy khi có bất thường và phải qua cooldown. Gọi LLM cho từng gói tin sẽ cháy
quota và làm dashboard đứng hình.

## WebSocket — `ws://localhost:8000/ws/telemetry`

Mọi message đều đúng một envelope, không ngoại lệ:

```jsonc
{ "type": "...", "ts": 1786859573.0, "payload": { ... } }
```

| `type` | Khi nào | `payload` |
|---|---|---|
| `snapshot` | Ngay khi client kết nối, rồi lặp lại mỗi 10s | Toàn bộ thiết bị: `{SOIL_01: {name, units, latest, is_stale, rolling}, ...}` |
| `telemetry` | Mỗi bản ghi mới | `{device_code, name, units, metrics, latest, is_stale, source, scenario}` |
| `anomaly` | Model báo bất thường | `{device_code, name, reading, rolling, is_anomaly, anomaly_score, confidence, metrics_used}` |
| `agent_insight` | Agent chẩn đoán xong | `{trigger, device_code, anomaly, answer, trace, latency_ms}` |
| `plan` / `task` / `notification` | Có hành động được tạo | Nguyên object plan/task/notification |
| `guardrail_veto` | Guardrail cứng phủ quyết | `{action, reason}` |

`ts` lấy **event-time** từ payload cảm biến khi có, không phải giờ máy chủ.

`answer` trong `agent_insight` là văn xuôi tiếng Việt do LLM sinh; `trace` là danh sách
tool đã thực sự chạy kèm kết quả — đây là phần "giải thích quyết định" để hiển thị.

## REST chính

| Endpoint | Việc |
|---|---|
| `GET /api/status` | Tự chấm điều kiện "tối thiểu 4/6 thiết bị có dữ liệu" |
| `GET /api/health` | Trạng thái kết nối MQTT, số message, số client WS |
| `GET /api/devices` · `/{code}` · `/{code}/history` | Telemetry + rolling stats |
| `GET /api/analytics/irrigation-recommendation` | Khuyến nghị tưới: `ml_forecast` (còn bao lâu đất khô) + `anomaly` (z-score) + `safety_checks` (luật cứng) |
| `POST/GET /api/irrigation/plans` · `/{id}/approve` · `/{id}/reject` | Kế hoạch tưới + human-in-the-loop |
| `POST/GET /api/tasks` · `/{id}/complete` · `/{id}/verify` | Phiếu hiện trường + verification kèm chứng cứ telemetry |
| `GET /api/resources/water-budget` · `/staff` | Ngân sách nước, nhân sự |
| `POST /api/agent/request` | Hỏi Agent bằng tiếng Việt, trả `{answer, trace}` |
| `GET /api/agent/insights?limit=` | Incident Log — mọi chẩn đoán gần đây (mặc định 20, mới nhất trước), không chỉ cái cuối. Dashboard gọi lúc load, và làm dự phòng khi LLM chết |

### Demo (chuẩn bị sẵn cho pitch)

```bash
# Bơm sự cố — đi qua đúng đường ống như dữ liệu thật
curl -X POST localhost:8000/api/simulate/inject \
     -H 'Content-Type: application/json' \
     -d '{"device_code":"SOIL_01","metrics":{"soil_moisture":3.0}}'

# Kịch bản 3: cảm biến mất kết nối (giữ stale thật sự, kể cả khi broker vẫn đang gửi)
curl -X POST localhost:8000/api/simulate/freeze/SUN_01
curl -X POST localhost:8000/api/simulate/unfreeze/SUN_01
```

## Ghi chú cho người sửa tiếp

- **Đừng chạy `python -m app.mqtt_client` thành tiến trình riêng.** `farm_state` là biến
  RAM trong một process; tiến trình tách rời sẽ không bao giờ chia sẻ dữ liệu với uvicorn.
  MQTT client đã chạy sẵn trong thread nền cùng process.
- **Đừng subscribe chồng lấn topic.** Wildcard `hackathon/ae_mien_trung/#` đã phủ cả
  `test/` lẫn `judge/`; thêm subscription trùng sẽ khiến broker gửi mỗi message nhiều lần
  và làm hỏng rolling mean/std. `config.subscribe_topics()` đã tự lọc.
- **Thiết bị mới trong `DEVICES` cần thêm cả tham số phân phối** ở
  `app/ml/generate_normal_operating_data.py:NORMAL_PARAMS`, nếu không sẽ không có model
  anomaly (pipeline fail-soft, chỉ log cảnh báo một lần).
