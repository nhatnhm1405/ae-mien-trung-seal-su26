"""
Cấu hình toàn cục cho Data/Backend layer.

QUAN TRỌNG: Đây là file DUY NHẤT bạn cần sửa vào sáng Ngày 2 khi BTC công bố
địa chỉ MQTT broker + tên topic thật. Mọi chỗ khác trong code chỉ đọc từ đây,
không hardcode lại tên thiết bị hay topic ở nơi khác.
"""

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 1. MQTT broker — SỬA 3 DÒNG NÀY khi có thông tin thật từ BTC (Ngày 1)
# ---------------------------------------------------------------------------
MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883
MQTT_TOPIC_PREFIX = "farm"  # đoán: farm/<device_code>/telemetry — sửa theo thực tế

# Nếu BTC dùng 1 topic chung cho tất cả thiết bị thay vì mỗi thiết bị 1 topic,
# đổi USE_SINGLE_TOPIC = True và set SINGLE_TOPIC bên dưới.
USE_SINGLE_TOPIC = False
SINGLE_TOPIC = "farm/telemetry"


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
}

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
