"""
Farm Coordinator & Action Agent — Agent DUY NHẤT gọi LLM (qua llm_client.py).

Nhận 1 yêu cầu tiếng Việt của người quản lý, dùng LLM function-calling để điều
phối Field IoT Agent + Irrigation & Resource Agent (2 agent Python thuần bên
dưới), rồi tự gọi các Tool/API hành động trong app/tools.py (đã có sẵn
guardrail cứng + verification). Đây là nơi thực hiện chu trình:
Nhận yêu cầu → Đọc dữ liệu IoT → Phân công Agent → Phối hợp → Tool/API →
Verification → Báo cáo.
"""

from __future__ import annotations

from app import tools
from app.agents import field_iot_agent, irrigation_resource_agent, llm_client

# ---------------------------------------------------------------------------
# Tool schemas — mô tả cho LLM, đúng format function-calling của OpenAI SDK
# ---------------------------------------------------------------------------
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_farm_snapshot",
            "description": (
                "Đọc dữ liệu IoT mới nhất từ tất cả thiết bị (Field IoT Agent). "
                "BẮT BUỘC gọi tool này ĐẦU TIÊN, trước khi suy luận hay trả lời bất cứ điều gì. "
                "Trả về latest, rolling stats (mean/std/slope), is_stale, data_age_seconds cho từng thiết bị."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assess_irrigation_need",
            "description": (
                "Irrigation & Resource Agent: đánh giá có nên tưới không, dựa trên độ bất thường "
                "của độ ẩm đất (z-score tự học từ dữ liệu, không phải ngưỡng cố định) và guardrail "
                "cứng (bồn nước, pH, công suất bơm). Dùng cho yêu cầu lập kế hoạch tưới."
            ),
            "parameters": {
                "type": "object",
                "properties": {"zone": {"type": "string", "description": "Mã khu vực, ví dụ 'A'"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "review_irrigation_session",
            "description": (
                "Irrigation & Resource Agent: kiểm tra phiên tưới hiện tại/gần nhất có bất thường "
                "không, dựa trên PUMP_01, SOIL_01, TANK_01. Dùng cho yêu cầu kiểm tra sau khi tưới."
            ),
            "parameters": {
                "type": "object",
                "properties": {"zone": {"type": "string"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_irrigation_plan",
            "description": (
                "Action: tạo kế hoạch tưới CHÍNH THỨC (có guardrail cứng, có thể bị từ chối/VETO). "
                "CHỈ gọi khi assess_irrigation_need trả should_irrigate=true và guardrail không chặn."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "zone": {"type": "string"},
                    "scheduled_time": {
                        "type": "string",
                        "description": "Thời điểm tưới, ISO8601 hoặc mô tả rõ giờ",
                    },
                    "priority": {"type": "string", "enum": ["low", "normal", "high"]},
                    "rationale": {
                        "type": "string",
                        "description": "Giải thích ngắn gọn dựa trên số liệu IoT thực tế đã đọc được",
                    },
                    "used_devices": {"type": "array", "items": {"type": "string"}},
                    "duration_minutes": {"type": "integer", "default": 20},
                    "require_approval": {"type": "boolean", "default": True},
                },
                "required": ["zone", "scheduled_time", "priority", "rationale", "used_devices"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_inspection_task",
            "description": (
                "Action: tạo phiếu kiểm tra hiện trường. Dùng khi review_irrigation_session phát hiện "
                "bất thường, HOẶC khi có thiết bị stale/mất kết nối cần người ra kiểm tra — "
                "KHÔNG được tự suy diễn giá trị của thiết bị đã chết, phải tạo task này thay vào đó."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "zone": {"type": "string"},
                    "reason": {"type": "string"},
                    "used_devices": {"type": "array", "items": {"type": "string"}},
                    "severity": {"type": "string", "enum": ["normal", "urgent"], "default": "normal"},
                    "assigned_to": {"type": "string", "default": "field_team"},
                },
                "required": ["title", "zone", "reason", "used_devices"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_notification",
            "description": "Action: gửi thông báo ngắn tới dashboard/kênh khác.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "channel": {"type": "string", "default": "dashboard"},
                    "severity": {"type": "string", "enum": ["info", "warning", "critical"], "default": "info"},
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report",
            "description": "Action: tạo báo cáo tổng hợp canh tác (tự loại thiết bị stale, không bịa số).",
            "parameters": {
                "type": "object",
                "properties": {"zone": {"type": "string"}},
                "required": [],
            },
        },
    },
]

TOOL_IMPLS = {
    "get_farm_snapshot": lambda: field_iot_agent.get_farm_snapshot(),
    "assess_irrigation_need": irrigation_resource_agent.assess_irrigation_need,
    "review_irrigation_session": irrigation_resource_agent.review_irrigation_session,
    "create_irrigation_plan": tools.create_irrigation_plan,
    "create_inspection_task": tools.create_inspection_task,
    "send_notification": tools.send_notification,
    "generate_report": tools.generate_report,
}

# ---------------------------------------------------------------------------
# System prompt — nhấn đúng 3 kịch bản BTC chấm điểm trong TRACK_B_SMART_AGRICULTURE.txt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """Bạn là Farm Coordinator & Action Agent của hệ thống Multi-Agent nông nghiệp thông minh.
Bạn điều phối 2 agent khác thông qua tool: Field IoT Agent (đọc dữ liệu thô) và
Irrigation & Resource Agent (đánh giá/đề xuất, có guardrail). Chỉ mình bạn được gọi LLM;
2 agent kia là Python thuần, không tự suy diễn gì ngoài dữ liệu thật.

QUY TẮC BẮT BUỘC (không được vi phạm):
1. LUÔN gọi tool `get_farm_snapshot` ĐẦU TIÊN trong mọi yêu cầu, trước khi trả lời hay gọi
   bất kỳ tool nào khác. Mọi con số bạn nhắc tới trong câu trả lời PHẢI lấy từ kết quả tool
   trả về — không được tự bịa số liệu cảm biến.
2. Yêu cầu liên quan lập kế hoạch tưới: gọi `assess_irrigation_need` để lấy đề xuất (đã tính
   z-score độ ẩm đất + guardrail bồn nước/pH/bơm). CHỈ gọi `create_irrigation_plan` khi
   should_irrigate=true VÀ guardrail không VETO. Nếu bị VETO, giải thích lý do rõ ràng cho
   người dùng và KHÔNG tạo kế hoạch.
3. Yêu cầu liên quan kiểm tra phiên tưới đã/đang chạy: gọi `review_irrigation_session`. Nếu
   anomaly_found=true, PHẢI gọi `create_inspection_task` (severity="urgent" nếu liên quan an
   toàn bơm/guardrail, ngược lại "normal").
4. Nếu bất kỳ thiết bị nào trong snapshot có is_stale=true hoặc data_age_seconds lớn: KHÔNG
   ĐƯỢC suy diễn/ước lượng/bịa giá trị cho thiết bị đó. Tách rõ 2 phần trong câu trả lời:
   (a) phần vẫn xử lý được bằng dữ liệu từ thiết bị còn hoạt động, và (b) phần không đủ dữ
   liệu để kết luận. Với phần (b), PHẢI gọi `create_inspection_task` để cử người kiểm tra kết
   nối cảm biến — đây gọi là "chế độ xử lý một phần" (partial mode), không được báo cáo như
   thể mọi thứ bình thường.
5. Sau khi tạo plan/task quan trọng, có thể gọi `send_notification` để thông báo ngắn cho dashboard.
6. Nếu người dùng chỉ hỏi báo cáo/tổng hợp tình trạng, dùng `generate_report`.
7. Câu trả lời cuối cùng PHẢI bằng tiếng Việt, ngắn gọn, rõ ràng, và PHẢI nêu:
   - Số liệu IoT cụ thể nào đã ảnh hưởng quyết định (tên thiết bị + giá trị + độ mới dữ liệu).
   - Thiết bị nào đang stale/thiếu dữ liệu (nếu có) và task kiểm tra đã tạo (nếu có).
   - Kết quả guardrail (được phép/bị chặn) nếu có liên quan tới tưới tiêu/bơm.
   KHÔNG được đưa ra số liệu hoặc kết luận không có trong kết quả tool đã gọi.
"""


def handle_request(message: str) -> dict:
    """Điểm vào chính — nhận 1 câu yêu cầu tiếng Việt, trả về câu trả lời cuối + trace tool."""
    result = llm_client.run_tool_calling_loop(
        system_prompt=SYSTEM_PROMPT,
        user_message=message,
        tool_schemas=TOOL_SCHEMAS,
        tool_impls=TOOL_IMPLS,
    )
    return {"answer": result["final_text"], "trace": result["trace"]}
