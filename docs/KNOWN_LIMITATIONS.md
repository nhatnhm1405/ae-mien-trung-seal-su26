# KNOWN_LIMITATIONS.md — Thiếu sót & hạn chế sau khi fusion backend + frontend

> Ghi lại 16/08/2026 sau khi hợp nhất `llm-test` + `back-end` thành một backend
> duy nhất và nối frontend vào dữ liệu thật. Mọi thứ dưới đây đã được xác nhận
> bằng cách chạy thật (broker BTC + LLM thật), không phải suy đoán — trừ khi
> ghi rõ "chưa kiểm chứng".

---

## 1. Chưa làm — cần trước khi thi

### 1.1. [ĐÃ SỬA 16/08] Không có nút "Xác minh" trên UI
`POST /api/tasks/{id}/verify` đã hoạt động đúng từ trước (test bằng curl: trả
`verification_status: PASSED`, `confidence_score: 1.0`), và `useFarmData.ts`
đã có sẵn `actions.verifyTask()`. Nhưng **không có nút nào trong `App.tsx` gọi
nó** — cột "Xác minh gần nhất" chỉ hiện log suy ra từ plan/task đã đổi trạng
thái (`toVerificationViews`), không phải hành động xác minh thật do người dùng
bấm.

**Đã sửa:** thêm cột "Hành động" vào bảng Nhiệm vụ với nút "Xác minh" cho
từng task chưa qua verification (chỉ hiện khi có `task.id` thật, không hiện
trên dữ liệu mẫu). Sau khi bấm, nút đổi thành "Đã xác minh". Đã kiểm chứng
qua backend thật: `open` → `verified`, `verification_proof.verification_status
= "PASSED"`.

### 1.2. `.env.example` thiếu biến cấu hình mới
Sau khi hợp nhất, `app/config.py` đọc thêm `AGENT_COOLDOWN_SECONDS`,
`AGENT_ON_ANOMALY`, và có default cứng cho `MQTT_TOPIC_TEST` /
`MQTT_TOPIC_JUDGE` / `MQTT_TOPIC_WILDCARD` — nhưng `back-end/.env.example`
(thừa kế từ `llm-test/.env.example` cũ) chưa liệt kê các biến này. Không gây
lỗi (có default), nhưng người mới clone repo không biết các biến này tồn tại
để chỉnh khi cần (VD: tắt LLM giữa buổi thi vì hết quota).

### 1.3. Guardrail bơm không thực sự chặn hành động
`tools.check_pump_guardrail()` tồn tại và được **đọc** trong
`irrigation_resource_agent.assess_irrigation_need()` (ảnh hưởng
`should_irrigate`), nhưng `tools.create_irrigation_plan()` — hàm thực thi thật
— **chỉ gọi `check_irrigation_guardrail()`** (bồn nước + pH), không gọi
`check_pump_guardrail()`. Nghĩa là nếu công suất bơm vượt ngưỡng an toàn
(`max_pump_power_w`), Agent vẫn có thể tạo được kế hoạch tưới qua tool này —
guardrail bơm chỉ mang tính khuyến nghị, không phải chặn cứng.

**Cách sửa:** thêm `check_pump_guardrail()` vào đầu `create_irrigation_plan()`
giống cách `check_irrigation_guardrail()` đang làm.

---

## 1.5. [ĐÃ SỬA 16/08] Model anomaly báo động giả liên tục trên PH_01

**Triệu chứng quan sát qua UI:** chấm trạng thái PH_01 đỏ gần như vĩnh viễn,
không phản ánh đúng mức độ nghiêm trọng thực tế.

**Nguyên nhân gốc:** model train trên dữ liệu tổng hợp (`NORMAL_PARAMS` trong
`generate_normal_operating_data.py`) giả định pH dao động hẹp quanh 5.8–7.2.
Dữ liệu **thật** từ topic test của BTC dao động rộng hơn nhiều — đo được pH
nhảy 5.2 → 9.3 chỉ trong vài giây, thuộc bản chất dữ liệu thử nghiệm của BTC,
không phải lỗi cảm biến. Model coi gần hết các giá trị này là bất thường →
bắn cảnh báo trung bình mỗi 5 giây/lần → chấm đỏ không bao giờ hết hạn (TTL
120s luôn được làm mới).

**Đã sửa bằng cách nào:** chạy `python -m app.ml.live_train` trong ~100 giây
để thu thập 198 mẫu dữ liệu thật (đủ 6 thiết bị) và refit lại cả 6
`EllipticEnvelope`. Backend **không cần restart** — `anomaly_model._load()`
tự theo dõi mtime file `.pkl` và nạp lại model mới ngay khi phát hiện đổi.

**Kết quả kiểm chứng:** 30 giây sau retrain, 0 cảnh báo giả (trước đó 6
lần/30s). Model vẫn bắt đúng cực đoan thật khi test tay: `ph=1.0` →
`is_anomaly=True` (score -11.99), `ph=6.5/8.0` (trong dải thật) →
`is_anomaly=False`, `ph=9.5/12.0` → `True`.

**Rủi ro còn lại — cần lưu ý khi thi thật:**
- Việc retrain này chỉ áp dụng cho phiên dữ liệu vừa thu thập. Nếu BTC đổi
  hành vi dữ liệu giữa vòng bảng và vòng chung kết (khác "test" so với
  "judge" topic), cần chạy lại `live_train` với dữ liệu mới trước khi demo.
- `live_train.py` mở **một kết nối MQTT riêng** tới broker (không dùng chung
  connection với backend đang chạy) — chạy cùng lúc 2 client là bình thường,
  nhưng nếu BTC giới hạn số kết nối đồng thời/tài khoản thì có thể bị từ chối.
  Nên chạy `live_train` trước giờ thi, không chạy song song lúc demo.
- Ghi chú trong code (`live_train.py`) đã cảnh báo: cơ chế này **CHỈ** áp
  dụng cho `anomaly_model`, **KHÔNG** áp dụng cho `irrigation_model` — dữ liệu
  test của BTC dao động ngẫu nhiên quanh 0, không có xu hướng vật lý để học,
  refit `irrigation_model` bằng dữ liệu này từng cho MAE tệ hơn cả đoán trung
  bình (R² âm, đã thử nghiệm trước đó).

---

## 1.6. [ĐÃ SỬA 16/08] Chẩn đoán AI trước đó bị ghi đè mất, không xem lại được

**Triệu chứng:** panel "Chẩn đoán của AI" chỉ hiện được đúng 1 kết quả — Agent
chẩn đoán xong sự cố A, 2 phút sau sự cố B xảy ra và Agent chẩn đoán, thì chẩn
đoán A **biến mất hoàn toàn** khỏi cả UI lẫn API, không cách nào xem lại.

**Nguyên nhân gốc:** `pipeline.py` chỉ có 1 biến `last_insight: dict | None`
(không phải danh sách) — mỗi lần Agent chẩn đoán xong, dòng `last_insight =
insight` ghi đè thẳng lên bản trước. Phía frontend (`useFarmData.ts`) cũng chỉ
giữ `insight: AgentInsight | null` — 1 object duy nhất, message WS mới đè lên
message cũ trong state.

**Vì sao đây là gap thật, không chỉ thẩm mỹ:** bước 8 trong sequence diagram
của BTC (`docs/HACKATHON_CONTEXT.md`) ghi rõ *"Agent cập nhật **Incident Log**
và giải thích quyết định lên Dashboard"* — chữ "Log" ngụ ý một danh sách nhiều
sự cố theo thời gian, không phải chỉ giữ bản ghi cuối. Demo 2 kịch bản liên
tiếp (VD: hạn hán SOIL_01 rồi VETO PH_01) để khoe cả 2 case cho giám khảo thì
kịch bản đầu sẽ trôi mất trước khi kịp trình bày xong kịch bản 2.

**Đã sửa:**
- Backend: `pipeline.py` đổi `last_insight` (1 object) thành `insight_log`
  (deque, `maxlen=INSIGHT_LOG_MAXLEN=30`, mới nhất ở đầu), gắn `id` tăng dần +
  `ts` cho mỗi bản ghi, thread-safe bằng lock riêng (nhiều thiết bị bất thường
  cùng lúc → nhiều thread `_run_agent` chạy song song). Endpoint đổi từ
  `GET /api/agent/last-insight` thành `GET /api/agent/insights?limit=` trả về
  danh sách.
- Frontend: `useFarmData.ts` đổi `insight` thành `insights: AgentInsight[]`,
  message WS mới được **chèn vào đầu** mảng (có dedupe theo `id`) thay vì đè.
  `AiPanel.tsx` tách thành `InsightCard` (1 thẻ đầy đủ) dùng cho bản ghi mới
  nhất (luôn mở rộng) + danh sách "Lịch sử chẩn đoán" thu gọn bên dưới (bấm để
  mở chi tiết từng cái, không giới hạn chỉ mở 1 cái tại một thời điểm — để có
  thể so sánh 2 kịch bản cùng lúc lúc pitch).

**Kiểm chứng:** kích hoạt 3 sự cố liên tiếp (SOIL_01, rồi PH_01, cách nhau
~35s) trên backend thật — cả 3 đều còn nguyên trong `/api/agent/insights`
(id 1–7, có cả vài cái tự phát sinh từ dữ liệu thật xen giữa), đúng thứ tự
mới nhất trước, không cái nào bị mất.

---

## 2. Đã biết nhưng chấp nhận được cho hackathon 7 tiếng

### 2.1. Agent chậm — 24.7 giây cho 1 lần chẩn đoán
Đo thật lúc test: Coordinator Agent chạy 6 vòng tool-calling mất 24.7s. Với
pitch 5 phút (90 giây dành cho "khoảnh khắc quyết định"), đây gần như hết luôn
thời gian dành cho phần này.

**Chưa sửa vì:** cần cân nhắc đánh đổi giữa tốc độ và độ đầy đủ của trace tool
(nhiều tool hơn = giải thích thuyết phục hơn nhưng chậm hơn). Nếu cần rút ngắn:
giảm `MAX_TOOL_ROUNDS` trong `llm_client.py` (hiện là 6), hoặc cho phép
Coordinator "tắt" bước `review_irrigation_session` khi đã có đủ context từ
`assess_irrigation_need`.

### 2.2. `answer` của Agent đôi khi lộ suy nghĩ nội bộ
Quan sát thật: một câu trả lời chứa nguyên văn *"Tôi đã có đầy đủ thông tin...
Giờ tôi tổng hợp câu trả lời tiếng Việt."* — đây là lỗi prompt (model đang
"nghĩ thành lời" thay vì chỉ trả kết quả cuối). `AiPanel.tsx` vẫn render được
nhưng câu đó lộ ra trước mặt giám khảo.

**Cách sửa:** thêm chỉ dẫn rõ trong `SYSTEM_PROMPT` (coordinator_agent.py):
"Không diễn giải quá trình suy nghĩ, chỉ trả kết luận cuối."

### 2.3. `agent_insight.answer` là văn xuôi tự do, không phải JSON có cấu trúc
`AiPanel.tsx` có renderer markdown tối giản để hiển thị được, nhưng frontend
không thể trích riêng từng trường `root_cause` / `severity` /
`recommended_action` để hiển thị dạng field tách bạch — phải đọc nguyên khối
văn bản. Muốn có cấu trúc thật sự phải sửa `SYSTEM_PROMPT` để ép model trả JSON
kèm một trường `narrative` riêng cho phần diễn giải.

### 2.4. Race giữa cảnh báo và dữ liệu hiện tại
Với dữ liệu **thật** từ broker (không phải inject), pin 20 giây chỉ áp dụng
cho nguồn `inject` (đã sửa trong phiên này) — dữ liệu thật vẫn cập nhật liên
tục trong lúc Agent đang chẩn đoán (1–3s+). Quan sát thật: Agent nhận anomaly ở
`ph=4.7` nhưng lúc đọc snapshot đã thấy `ph=7.0`. Agent tự nhận ra mâu thuẫn và
xử lý hợp lý (tạo task "urgent" thay vì tự suy diễn), nhưng đây là hành vi cố
hữu của hệ thống streaming thật, không phải bug — cần biết để không hoảng khi
thấy log có vẻ "mâu thuẫn".

### 2.5. Không có test tự động
Toàn bộ việc xác minh trong phiên fusion này làm bằng script curl/Python/
Node thủ công (xem lịch sử — không có file test còn lại trong repo). Không có
`pytest` cho backend, không có test frontend. Nếu có thời gian, ít nhất nên có
1 test cho `parse_payload()` (MQTT) và 1 test cho `adapt.ts` (dịch shape dữ
liệu) — đây là hai chỗ dễ vỡ nhất khi BTC đổi schema payload phút chót.

### 2.6. Chưa xác nhận bằng mắt trên trình duyệt thật
Mọi kiểm chứng frontend trong phiên này là: `tsc --noEmit`, `npm run build`,
SSR smoke test (`renderToString`), và chạy logic adapter trực tiếp trên dữ
liệu sống qua script Node — **không phải** mở Chrome và nhìn. Extension
Chrome không kết nối được lúc đó. Về mặt logic dữ liệu đã đúng, nhưng chưa ai
xác nhận bố cục, màu sắc, animation, hoặc lỗi runtime chỉ xuất hiện khi
hydrate trong trình duyệt thật.

---

## 3. Giới hạn kiến trúc (chấp nhận được, nhưng nên biết)

### 3.1. Không lưu trữ bền vững
`farm_state` là biến RAM thuần tuý. Restart backend = mất toàn bộ plans,
tasks, notifications, và lịch sử telemetry (deque). Đây là lựa chọn cố ý theo
khuyến nghị "đơn giản hoá triệt để" của `HACKATHON_CONTEXT.md`, nhưng nghĩa là
**không được restart backend giữa lúc demo** — mất hết context vừa build lên
trong lúc trình bày.

### 3.2. Không có concurrency limit toàn cục cho tầng LLM
`AGENT_COOLDOWN_SECONDS` (mặc định 60s) chỉ giới hạn theo **từng thiết bị**.
Nếu 3–4 thiết bị cùng bất thường một lúc (VD: BTC bơm kịch bản "mất điện toàn
trại"), có thể có 3–4 lời gọi LLM chạy song song cùng lúc — không có giới hạn
tổng số request đồng thời. Rủi ro cháy quota nhanh hơn dự tính nếu BTC test
kịch bản nhiều thiết bị cùng lỗi.

### 3.3. REST không có xác thực
Mọi endpoint — kể cả `/api/simulate/inject`, `/api/irrigation/plans/*/approve`
— mở hoàn toàn, không cần token. CORS `allow_origins=["*"]`. Chấp nhận được
cho demo hackathon trong mạng nội bộ, nhưng nếu backend lỡ expose ra internet
công khai thì ai cũng bơm được dữ liệu giả hoặc tự duyệt kế hoạch tưới.

### 3.4. Hai simulator riêng biệt, không dùng chung code
`app/mqtt_client.py:start_simulator()` (chạy nền khi `SIMULATE=true`, dùng
runtime chính) và `back-end/simulator.py` (script CLI độc lập,
`BTCFarmSimulator`, dùng để test format payload BTC) là hai cách sinh dữ liệu
giả **khác nhau hoàn toàn**, không chia sẻ logic. Không sai, nhưng dễ nhầm khi
có người mới đọc code và thấy "ơ sao có 2 simulator".

### 3.5. Nhãn metric tiếng Việt hardcode theo tên field
`front-end/src/lib/adapt.ts:METRIC_LABEL` map cứng `soil_moisture` →
"Độ ẩm đất" v.v. Nếu BTC đổi tên field trong payload thật (khác với
`hackathon/ae_mien_trung/test/telemetry` đã test), UI sẽ hiện fallback là
chính tên field tiếng Anh thay vì nhãn tiếng Việt — không vỡ, nhưng xấu.

### 3.6. Ngưỡng "cảnh báo hết hạn" cố định 120 giây ở frontend
`ANOMALY_TTL_MS = 120_000` trong `adapt.ts` — sau 2 phút, card thiết bị tự hết
đỏ dù bất thường vẫn còn (nếu không có message mới xác nhận). Nếu phần Q&A sau
demo kéo dài hơn 2 phút mà giám khảo hỏi lại về sự cố vừa demo, dashboard sẽ
không còn hiện đỏ nữa — cần bấm lại nút "Bơm sự cố" nếu muốn minh hoạ lại.

---

## 4. Rủi ro bảo mật (không chặn thi, nhưng nên biết)

### 4.1. Credential từng bị hardcode trong lịch sử git
File `back-end/mqtt_client.py` (đã bị xoá trong lúc fusion) từng có mật khẩu
MQTT và test key làm giá trị mặc định ngay trong code:
```python
PASSWORD = os.getenv("MQTT_PASSWORD", "mq_2fXRJxD_lAVgHEXTMF33JQ")
TEST_KEY = os.getenv("MQTT_TEST_KEY", "tk_CgukidjWBbI2A-ev1MZpCE2yLOBhwiR7")
```
File đã xoá khỏi working tree nhưng **vẫn còn trong lịch sử commit** trên
`origin/develop` và `origin/main`. Nếu repo này public hoặc BTC/đối thủ có thể
xem lịch sử git, nên cân nhắc đổi credential với BTC.

### 4.2. `.env` chứa API key thật ở dạng plaintext
`OPENAI_API_KEY` (key DeepSeek thật) nằm trong `back-end/.env` — file này
**không** bị commit (đã xác nhận nằm trong `.gitignore` và `git status`
không track nó), nhưng nó tồn tại trên máy local dưới dạng plaintext, không
mã hoá. Bình thường cho môi trường demo, chỉ cần nhớ xoá/đổi key sau khi thi
nếu máy đó dùng chung.

---

## 5. Vấn đề vận hành đã gặp (không phải bug code, nhưng tốn thời gian nếu không biết trước)

### 5.1. PowerShell khác Bash — 2 lỗi đã gặp thật khi vận hành
- `SIMULATE=false uvicorn ...` (cú pháp bash set biến môi trường inline)
  **không chạy được** trên PowerShell. Phải tách 2 dòng:
  ```powershell
  $env:SIMULATE = "false"
  python -m uvicorn app.main:app --port 8000
  ```
- `uvicorn` không nằm trong PATH khi gọi trực tiếp trên máy đã test — phải gọi
  qua `python -m uvicorn` thay vì `uvicorn` trần.

Nên cập nhật `back-end/README.md` với cả 2 biến thể lệnh (bash và PowerShell)
để đồng đội không vấp lại đúng lỗi này giữa lúc chuẩn bị thi.

---

## Tóm tắt ưu tiên nếu còn thời gian trước khi thi

1. **Bắt buộc trước MỖI lần thi (vòng bảng lẫn chung kết):** chạy lại
   `python -m app.ml.live_train` khoảng 1–2 phút ngay khi có dữ liệu thật từ
   BTC, trước khi demo (§1.5) — nếu không PH_01 (và có thể thiết bị khác) sẽ
   đỏ liên tục do model train trên dữ liệu tổng hợp có dải hẹp hơn thực tế.
2. ~~Thêm nút "Xác minh" vào bảng Nhiệm vụ~~ — **đã sửa** (§1.1).
3. **Còn tồn đọng, chưa sửa (đã quyết định giữ nguyên):** guardrail bơm chỉ
   trang trí, không chặn thật khi tạo kế hoạch tưới qua tool
   (§1.3) — `check_pump_guardrail()` chưa được gọi trong
   `create_irrigation_plan()`.
4. **Nên làm:** cập nhật `.env.example` (§1.2) và `README.md` với lệnh
   PowerShell (§5.1) — tránh đồng đội mất thời gian debug lệnh sai cú pháp
   ngay trước giờ thi.
5. **Nếu rảnh:** rút ngắn `MAX_TOOL_ROUNDS` hoặc sửa `SYSTEM_PROMPT` (§2.1,
   §2.2) để Agent nhanh hơn và không lộ suy nghĩ nội bộ.
6. **Bắt buộc trước khi thi thật:** mở trình duyệt thật xem giao diện ít nhất
   một lần (§2.6) — chưa ai xác nhận bằng mắt.
7. ~~Chẩn đoán AI trước đó bị ghi đè mất~~ — **đã sửa**, giờ là Incident Log
   giữ tối đa 30 bản ghi (§1.6).
