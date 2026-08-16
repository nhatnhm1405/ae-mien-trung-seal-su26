"""
Cấu hình toàn cục cho Data/Backend layer.

QUAN TRỌNG: Đây là file DUY NHẤT bạn cần sửa khi BTC công bố địa chỉ MQTT
broker + tên topic thật. Mọi chỗ khác trong code chỉ đọc từ đây, không
hardcode lại tên thiết bị hay topic ở nơi khác.

Giá trị thật (host, username, password, topic...) KHÔNG nằm trong file này —
nằm trong `.env` (đã bị .gitignore chặn, không commit). File này chỉ đọc qua
os.environ / python-dotenv. Copy `.env.example` -> `.env` rồi điền nếu chưa có.
"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()  # nạp back-end/.env khi chạy uvicorn từ trong thư mục back-end/


# ---------------------------------------------------------------------------
# 1. MQTT broker — lấy từ .env, KHÔNG hardcode credential thật ở đây
# ---------------------------------------------------------------------------
# MQTT_BROKER_HOST là tên chuẩn; MQTT_BROKER giữ lại làm alias vì .env hiện có
# đang dùng tên đó (back-end/mqtt_client.py cũ đọc MQTT_BROKER).
MQTT_BROKER_HOST = os.environ.get("MQTT_BROKER_HOST") or os.environ.get("MQTT_BROKER", "localhost")
MQTT_BROKER_PORT = int(os.environ.get("MQTT_BROKER_PORT") or os.environ.get("MQTT_PORT", "1883"))

MQTT_USERNAME = os.environ.get("MQTT_USERNAME")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")
MQTT_TEST_KEY = os.environ.get("MQTT_TEST_KEY")  # chưa rõ mục đích, xem ghi chú README

# Broker BTC chạy sau Cloudflare trên cổng 443 -> xác nhận qua MQTTX là bắt buộc
# dùng MQTT over WebSocket Secure (wss), không phải TCP thuần như mặc định paho-mqtt.
# Cổng 443 thì mặc định luôn là websockets + TLS, kể cả khi .env không khai báo.
MQTT_TRANSPORT = os.environ.get(
    "MQTT_TRANSPORT", "websockets" if MQTT_BROKER_PORT == 443 else "tcp"
)
MQTT_USE_TLS = (
    os.environ.get("MQTT_USE_TLS", "true").lower() in ("true", "1", "yes")
    or MQTT_BROKER_PORT == 443
)
MQTT_WS_PATH = os.environ.get("MQTT_WS_PATH", "/mqtt")  # chỉ dùng khi MQTT_TRANSPORT=websockets

# BTC cấp 1 topic test dùng chung cho toàn đội test kết nối, không phải 1 topic/thiết bị
# -> mặc định dùng chế độ single-topic; parse_payload() phải tự đọc device_code trong JSON.
MQTT_TOPIC_PREFIX = "farm"  # dự phòng nếu sau này đổi sang mỗi thiết bị 1 topic riêng
USE_SINGLE_TOPIC = True
SINGLE_TOPIC = os.environ.get("MQTT_TEST_TOPIC", "farm/telemetry")

# Topic thật của BTC. Subscribe cả 3: test (dùng chung lúc tập), judge (lúc chấm),
# và wildcard để không chết nếu BTC đổi hậu tố topic vào phút chót.
MQTT_TOPIC_TEST = os.environ.get("MQTT_TOPIC_TEST", "hackathon/ae_mien_trung/test/telemetry")
MQTT_TOPIC_JUDGE = os.environ.get("MQTT_TOPIC_JUDGE", "hackathon/ae_mien_trung/judge/telemetry")
MQTT_TOPIC_WILDCARD = os.environ.get("MQTT_TOPIC_WILDCARD", "hackathon/ae_mien_trung/#")


def _covered_by(topic: str, pattern: str) -> bool:
    """topic có khớp với subscription pattern (có wildcard +/#) không."""
    t_parts, p_parts = topic.split("/"), pattern.split("/")
    for i, p in enumerate(p_parts):
        if p == "#":
            return True
        if i >= len(t_parts):
            return False
        if p != "+" and p != t_parts[i]:
            return False
    return len(t_parts) == len(p_parts)


def subscribe_topics() -> list[str]:
    """Danh sách topic sẽ subscribe, ĐÃ loại các topic bị wildcard phủ.

    Quan trọng: KHÔNG được subscribe chồng lấn. Theo MQTT spec, khi một client có
    nhiều subscription cùng khớp một message thì broker được phép gửi một bản sao
    cho MỖI subscription — và phần lớn broker làm đúng vậy. Subscribe cả
    `.../test/telemetry` lẫn `.../#` nghĩa là mỗi bản ghi vào buffer 2 lần: rolling
    mean/std sai, tần suất bất thường tăng gấp đôi. Wildcard đã phủ test+judge nên
    chỉ giữ wildcard.
    """
    candidates = [MQTT_TOPIC_WILDCARD, MQTT_TOPIC_TEST, MQTT_TOPIC_JUDGE, SINGLE_TOPIC]
    out: list[str] = []
    for topic in candidates:
        if not topic or topic in out:
            continue
        if any(_covered_by(topic, kept) for kept in out):
            continue  # đã có subscription rộng hơn phủ topic này
        out.append(topic)
    return out


def topic_for(device_code: str) -> str:
    """Trả về topic MQTT tương ứng với 1 device code."""
    if USE_SINGLE_TOPIC:
        return SINGLE_TOPIC
    return f"{MQTT_TOPIC_PREFIX}/{device_code}/telemetry"


# ---------------------------------------------------------------------------
# 2. Danh mục thiết bị — đúng theo đề bài TRACK_B_SMART_AGRICULTURE
# ---------------------------------------------------------------------------
@dataclass
class DeviceSpec:
    code: str
    name: str
    metrics: list  # tên các metric thiết bị này phát ra
    units: dict = field(default_factory=dict)


DEVICES: dict[str, DeviceSpec] = {
    "SOIL_01": DeviceSpec(
        code="SOIL_01",
        name="Cảm biến đất khu A",
        metrics=["soil_moisture", "temperature"],
        units={"soil_moisture": "%", "temperature": "°C"},
    ),
    "WEATHER_01": DeviceSpec(
        code="WEATHER_01",
        name="Trạm thời tiết",
        metrics=["temperature", "humidity"],
        units={"temperature": "°C", "humidity": "%"},
    ),
    "PUMP_01": DeviceSpec(
        code="PUMP_01",
        name="Bơm tưới khu A",
        metrics=["flow_rate", "power"],
        units={"flow_rate": "L/min", "power": "W"},
    ),
    "PH_01": DeviceSpec(
        code="PH_01",
        name="Cảm biến pH bồn",
        metrics=["ph"],
        units={"ph": "pH"},
    ),
    "TANK_01": DeviceSpec(
        code="TANK_01",
        name="Bồn nước chính",
        metrics=["level"],
        units={"level": "%"},
    ),
    "SUN_01": DeviceSpec(
        code="SUN_01",
        name="Cảm biến nắng khu A",
        metrics=["lux"],
        units={"lux": "lx"},
    ),
    # Thiết bị thử nghiệm BTC bắn kèm trên topic test — không thuộc 6 thiết bị Track B,
    # nhưng phải có trong danh mục nếu không farm_state.ingest() sẽ loại và log spam
    # "thiết bị lạ" mỗi message.
    "AC_01": DeviceSpec(
        code="AC_01",
        name="Thiết bị điều hòa (BTC demo)",
        metrics=["power", "temperature"],
        units={"power": "W", "temperature": "°C"},
    ),
}

# 6 thiết bị Track B thật sự — dùng để tự chấm điều kiện "tối thiểu 4/6 thiết bị
# có dữ liệu", không tính AC_01 vào mẫu số.
TRACK_B_DEVICES = ["SOIL_01", "WEATHER_01", "PUMP_01", "PH_01", "TANK_01", "SUN_01"]

# ---------------------------------------------------------------------------
# 3. Tham số windowing — đúng theo thông số BTC "đã chốt sẵn" trong slide
# ---------------------------------------------------------------------------
WATERMARK_SECONDS = 5
TUMBLING_WINDOW_SECONDS = 60
SLIDING_WINDOW_SECONDS = 300
SLIDING_STEP_SECONDS = 60

# Sau bao lâu không có dữ liệu mới thì coi là "stale" (kịch bản 3: gián đoạn dữ liệu)
STALE_THRESHOLD_SECONDS = 90

# Buffer RAM giữ tối đa bao nhiêu bản ghi / thiết bị (thay Redis Streams)
BUFFER_MAXLEN = 1000

# ---------------------------------------------------------------------------
# 4. Deterministic guardrail — luật cứng chặn giữa Agent và hành động vật lý
# ---------------------------------------------------------------------------
# Đây chính là "Deterministic Guardrail" trong file context — rẻ, ~20 dòng,
# nhưng rất ăn điểm khi giải thích trong pitch. LLM không có quyền phủ quyết.
GUARDRAILS = {
    # Không cho tạo lệnh tưới nếu bồn nước dưới ngưỡng này
    "min_tank_level_to_irrigate": 15.0,   # %
    # Không cho tạo lệnh tưới nếu pH nước ngoài khoảng an toàn
    "ph_safe_range": (5.5, 7.5),
    # Không cho bật bơm nếu công suất vượt ngưỡng (nghi bơm lỗi / kẹt)
    "max_pump_power_w": 2200.0,
}

# ---------------------------------------------------------------------------
# 5. Pipeline realtime — ML chạy mọi điểm, LLM chỉ chạy khi có bất thường
# ---------------------------------------------------------------------------
# Phát hiện bất thường rẻ (<1ms) -> chạy trên MỌI điểm dữ liệu.
# LLM đắt (1-3s) -> chỉ chạy khi có bất thường, và cùng 1 thiết bị phải chờ hết
# cooldown mới được gọi lần nữa. Không có cooldown = cháy quota + dashboard đứng hình.
AGENT_COOLDOWN_SECONDS = float(os.environ.get("AGENT_COOLDOWN_SECONDS", "60"))

# Bật/tắt tầng LLM trong pipeline. Tắt (false) thì vẫn có anomaly detection + broadcast,
# chỉ không gọi LLM — dùng khi hết quota hoặc mất mạng lúc demo.
AGENT_ON_ANOMALY = os.environ.get("AGENT_ON_ANOMALY", "true").lower() in ("true", "1", "yes")
