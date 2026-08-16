# HACKATHON_CONTEXT.md

> **Mục đích của file này**
> Đây là bản tổng hợp toàn bộ bối cảnh và chiến lược cho cuộc thi SEAL Hackathon Summer 2026.
> Dán file này vào đầu một cuộc trò chuyện mới để trợ lý AI nắm được ngay bối cảnh mà không cần giải thích lại.
>
> **Người dùng:** sinh viên CNTT chuẩn bị dự thi, xuất phát điểm chưa có nền về IoT streaming / stream processing.
> **Ngôn ngữ trao đổi:** tiếng Việt.
> **Track đã xác nhận: TRACK B — SMART AGRICULTURE** (Multi-Agent Farm Operations & Resource Coordination). Đề bài đầy đủ nằm ở `docs/TRACK_B_SMART_AGRICULTURE.txt` — đó mới là đề THẬT, file này chỉ là lớp chiến lược/từ vựng bọc quanh nó. Mọi phần bên dưới đã được chỉnh lại theo đúng đề Track B, không còn là suy đoán chung chung cho "IoT bất kỳ" nữa.
> **Đã loại trừ:** phần thảo luận về kiến trúc multi-agent cho track logistics (chỉ là ví dụ minh hoạ trước khi bốc thăm, không thuộc bối cảnh chung nữa).

---

## 1. Thông tin cuộc thi

**Tên:** SEAL Hackathon Summer 2026 (Software Engineering Agile League)
**Đơn vị tổ chức:** Trường Đại học FPT cơ sở TP.HCM
**Đối tượng:** Sinh viên CNTT tại ĐH FPT HCM và các trường ĐH khác tại TP.HCM (theo thư mời). Sinh viên đã tốt nghiệp không được tham gia.

**Chủ đề chung:** *"AI-Driven Smart Operations: Turning Real-Time IoT Data into Intelligent Actions"*
**Track của đội:** Track B — Smart Agriculture (xem chi tiết mục 3).

**Hệ thống Hackathon:** SEAL tổ chức 3 kỳ mỗi năm — Emerging Technologies, Product & User Experience, SDLC & Professional Working. Có 3 loại bảng xếp hạng: Chapter (cộng dồn cả năm), Team (từng kỳ, không cộng dồn), Cá nhân (cộng dồn cả năm).

### Cấu trúc thi đấu

- **3 Track**, mỗi Track là một lĩnh vực vận hành thông minh khác nhau. Đội mình đã bốc thăm được **Track B**.
- Mỗi Track là một bảng, tối đa 8 đội/bảng.
- Top 2 mỗi bảng vào chung kết → tổng 6 đội.

### Lịch trình

**Ngày 1 (14h00 – 17h00):** Khai mạc, phổ biến thể lệ, bốc thăm Track, công bố chủ đề, chia bảng. Mỗi đội nhận repository, tài khoản, thông tin kết nối hệ thống mô phỏng. Kiểm tra internet, API, MQTT, môi trường phát triển.
→ **Bắt buộc toàn bộ thành viên có mặt.**

**Ngày 2:**
| Khung giờ | Nội dung |
|---|---|
| 07h00 – 14h00 | Thi đấu chính thức (chỉ **7 tiếng** code) |
| 14h00 – 15h30 | Trình bày và chấm điểm vòng bảng (5 phút trình bày + 3 phút Q&A) |
| 15h30 – 17h00 | Vòng chung kết (7 phút trình bày + 3 phút Q&A) |
| 17h00 – 18h00 | Trao giải và bế mạc |

### Tiêu chí chấm điểm

**Vòng bảng:**
| Tiêu chí | Trọng số |
|---|---|
| Xử lý dữ liệu thời gian thực và độ chính xác | 30% |
| Hiệu quả ứng dụng AI | 30% |
| Tính phù hợp với Domain và trải nghiệm người dùng | 20% |
| Ý tưởng, Demo và Pitching | 20% |

**Vòng chung kết:**
| Tiêu chí | Trọng số |
|---|---|
| Độ hoàn thiện và ổn định của sản phẩm | 30% |
| Năng lực phân tích và hỗ trợ quyết định của AI | 30% |
| Tính sáng tạo, khả năng mở rộng và ứng dụng thực tế | 20% |
| Kỹ năng Demo, trình bày và phản biện | 20% |

### Quy định quan trọng

- Đến trễ quá 60 phút → không được tham gia.
- Mã nguồn phải trên GitHub/GitLab; tài liệu qua Jira/Confluence/Notion.
- Được dùng TensorFlow, PyTorch, scikit-learn, Hugging Face, OpenAI SDK, Google Gemini SDK, LangGraph hoặc tương đương.
- Một thí sinh chỉ tham gia một đội. Sau hạn đăng ký **không được đổi thành viên**.
- Không được rời khu vực thi đấu trong suốt thời gian thi.
- Bản quyền sản phẩm thuộc đội; BTC được dùng cho truyền thông và đào tạo.

### CẠM BẪY LỚN NHẤT (Điều 3)

> *"Sản phẩm chỉ trực quan hóa dữ liệu hoặc cảnh báo bằng điều kiện cố định sẽ không được xem là đáp ứng đầy đủ yêu cầu về AI."*

Dashboard đẹp + `if (soil_moisture < 20) alert()` = mất phần lớn 60% điểm (30% "Hiệu quả ứng dụng AI" + 30% "Xử lý dữ liệu thời gian thực").
**Bắt buộc phải có model/Agent học và suy luận từ dữ liệu, không hardcode ngưỡng ra quyết định.** (Guardrail cứng dạng if-else vẫn được phép — nhưng chỉ đóng vai trò *chặn* hành động nguy hiểm, không được đóng vai trò *ra quyết định chính*. Xem "Deterministic Guardrail" ở mục 2.2.)

---

## 2. Nội dung Workshop đã được giải mã

Workshop có 5 phần (Smart Operations Evolution, Real-Time Streaming Pipeline, AI Engine & Agentic Workflows, End-to-End Reference Architecture, Live Q&A). Người dùng phản hồi là diễn giả chỉ đọc slide và khó hiểu — slide viết cho kỹ sư hạ tầng đã có nền, không phải cho người học từ đầu.

**Đánh giá tổng quát: khoảng 80% nội dung slide là kiến trúc production cấp doanh nghiệp, KHÔNG dùng được trong 7 tiếng. Nhưng cần hiểu để nói đúng ngôn ngữ với giám khảo.**

### 2.1. Khung tư tưởng — 3 đời của Operational Monitoring

Đây là khung xuyên suốt cuộc thi và cũng là bố cục pitch:

1. **Passive Monitoring** ("Chuyện gì đã xảy ra?") — có dashboard, người ngồi nhìn 24/7. Độ trễ phát hiện sự cố rất cao.
2. **Reactive Alerting** ("Có đang hỏng không?") — luật IF-THEN với ngưỡng tĩnh. Vấn đề: báo động giả liên tục (alert fatigue) và **không bắt được suy thoái từ từ**.
3. **AI-Driven Smart Ops** ("Tại sao và sửa thế nào?") — phát hiện bất thường liên tục, phân tích nguyên nhân gốc tự động, vòng lặp khép kín.

→ Điều 3 chính là lệnh cấm nộp sản phẩm đời 2. Với Track B, "đời 3" thể hiện qua **chu trình multi-agent** ở mục 3, không phải qua closed-loop PLC như các track công nghiệp khác.

### 2.2. Từ điển thuật ngữ

**Telemetry** — số liệu cảm biến gửi về liên tục. Với Track B: `soil_moisture`, `temperature`, `humidity`, `flow_rate`, `power`, `ph`, `level`, `lux` (xem bảng thiết bị ở mục 3.3).

**MQTT (cổng 1883, TCP)** — giao thức pub/sub cho IoT. Cảm biến publish lên *topic*, ai cần thì subscribe, ở giữa có *broker* làm bưu điện. QoS 0 = có thể mất; QoS 1 = đảm bảo tới nhưng có thể trùng (**khuyến nghị dùng**); QoS 2 = đúng một lần, chậm. Thư viện: `paho-mqtt`.

**CoAP, Kafka/Redpanda** — có nhắc trong slide chung của BTC nhưng **đề Track B không đề cập container/broker cụ thể nào** (khác với track khác từng thấy giả lập kiểu weather-station). Đừng giả định có sẵn Kafka/Redpanda cho Track B — cứ chờ thông tin kết nối thật ở Ngày 1, và có phương án buffer thuần Python (`deque`) để không phụ thuộc.

**Windowing** — cắt dòng dữ liệu vô tận thành khúc để tính toán:
- *Tumbling window (60s)*: các khúc không chồng lấn. Dùng tính thống kê nền.
- *Sliding window (300s, trượt 60s)*: các cửa sổ chồng lấn 80%. Dùng bắt **xu hướng và độ dốc**.
- Ví dụ áp dụng cho Track B: độ ẩm đất 42% là bình thường, nhưng đang **giảm 5%/giờ** liên tục nghĩa là cây sắp thiếu nước dù số hiện tại chưa báo động — chỉ sliding window thấy được xu hướng này.
- Trong pandas cả hai chỉ là `df.rolling()` với tham số khác nhau. Đã có sẵn trong `llm-test/app/state.py::rolling_stats()`.

**Event-time vs Processing-time** — dữ liệu sinh lúc 9:00:08 nhưng tới nơi 9:00:12. **Luôn dùng timestamp cảm biến gắn trong payload**, không dùng giờ hệ thống.

**Watermark (5s)** — quy ước "chờ tối đa 5 giây rồi chốt sổ cửa sổ, ai tới trễ hơn cho ra luồng riêng (side-output)".

**Hot / Cold Storage:**
- *Redis Streams (slide)* → **thực tế đang dùng:** `deque` trong RAM (`llm-test/app/state.py`), giữ tối đa 1000 bản ghi/thiết bị, cho Agent đọc suy luận tức thời.
- *TimescaleDB/InfluxDB (slide)* → nếu cần lưu lâu dài, dùng file CSV/SQLite là đủ cho 7 tiếng.

**Isolation Forest** — phát hiện bất thường **không cần nhãn**. Trực giác: chặt ngẫu nhiên không gian dữ liệu bằng các nhát cắt. Điểm bình thường nằm giữa đám đông cần nhiều nhát mới cô lập; điểm dị thường nằm chơ vơ chỉ cần vài nhát. Số nhát cắt = điểm bất thường. Chạy CPU, `sklearn.ensemble.IsolationForest`, `contamination=0.03`. **Đây là lựa chọn đúng cho 7 tiếng** — dùng cho Field IoT Agent / Irrigation Planning Agent để tự học ngưỡng độ ẩm đất/pH/mực nước bất thường thay vì hardcode.

**Autoencoder / FFT** — bỏ qua trong 7 tiếng, không cần cho domain nông nghiệp (không có cảm biến rung tần số cao).

**SHAP** — sau khi model kêu "bất thường", SHAP trả lời "vì cảm biến nào" (VD: độ ẩm đất 70%, pH 20%, nhiệt độ 10%). `pip install shap`, chạy được ngay với model sklearn. **Rẻ và trông rất chuyên nghiệp — nên làm nếu còn thời gian, không bắt buộc cho Track B** (đề chỉ yêu cầu "thể hiện rõ dữ liệu IoT đã ảnh hưởng đến quyết định nào", không bắt buộc SHAP cụ thể — `data_snapshot` lưu trong mỗi plan/task đã đáp ứng đủ).

**Causal DAG / Root Cause Analysis** — Track B không yêu cầu causal DAG phức tạp, chỉ cần Agent **phân biệt được nguyên nhân với triệu chứng** khi dữ liệu gián đoạn (xem Kịch bản 3, mục 3.4) — ví dụ cảm biến ngừng cập nhật ≠ tình trạng đất thực sự bất thường.

**Function Calling** — mô tả cho LLM danh sách "công cụ" nó được gọi; LLM trả về tên hàm + tham số thay vì văn xuôi. Đây là cách các Agent trong Track B gọi `app/tools.py` (tạo kế hoạch tưới, tạo task, gửi thông báo).

**SOP (Standard Operating Procedure)** — quy trình vận hành chuẩn. Trong sản phẩm chỉ là file JSON/markdown kiểu "nếu độ ẩm đất < X và không mưa dự báo thì ưu tiên tưới", nhét vào prompt của Irrigation Planning Agent làm ngữ cảnh.

**Deterministic Guardrail** — tầng luật cứng **bằng Python thuần** chặn giữa Agent/LLM và hành động thực thi. **Đã implement sẵn** trong `llm-test/app/tools.py::check_irrigation_guardrail()` / `check_pump_guardrail()`: từ chối lệnh tưới nếu bồn nước < 15%, pH ngoài khoảng 5.5–7.5, hoặc công suất bơm > 2200W (nghi kẹt/lỗi). Agent/LLM **không có quyền phủ quyết** tầng này. Rất ăn điểm khi nói trong pitch — dùng đúng câu chữ "VETO: ..." đã có sẵn trong code.

**Dual-Mode Execution:**
- *Fully Autonomous* — nhiệm vụ không đảo ngược nguy hiểm gì (VD: tạo phiếu kiểm tra) → tự động hoàn toàn.
- *Human-in-the-loop* — kế hoạch tưới quan trọng thì cần người quản lý bấm Approve (đã có `require_approval` + `POST /api/irrigation/plan/{id}/approve` trong backend).
→ Track B **yêu cầu rõ trong đề**: "Có khu vực phê duyệt kế hoạch hoặc hành động quan trọng" (mục 7 — Yêu cầu UX).

### 2.3. Trình tự xử lý — áp dụng cho multi-agent Track B

Sequence gốc của BTC (Edge Detector → Event Stream → single AI Decision Agent → PLC) được thiết kế cho track công nghiệp/closed-loop. **Track B thay bằng chu trình multi-agent chính thức trong đề** (mục 4 của `TRACK_B_SMART_AGRICULTURE.txt`):

```
Nhận yêu cầu → Đọc dữ liệu IoT → Phân công Agent → Phối hợp → Tool/API → Verification → Báo cáo
```

Ánh xạ sang kiến trúc đội đang xây (mục 3.5 và 4 bên dưới):
1. Người quản lý gửi yêu cầu (VD: "chuẩn bị kế hoạch tưới cho khu A hôm nay").
2. **Field IoT Agent** đọc `GET /api/devices` — dữ liệu 6 thiết bị + rolling stats.
3. **Farm Coordinator Agent** phân việc cho Irrigation Planning Agent / Resource Agent.
4. Các Agent phối hợp: Irrigation Planning Agent đề xuất thời điểm/ưu tiên, Resource Agent kiểm tra ràng buộc nguồn nước.
5. **Farm Action Agent** gọi Tool/API (`POST /api/irrigation/plan`, có Deterministic Guardrail chặn trước) — đây là bước "hành động".
6. **Verification**: đọc lại ngay (`GET /api/irrigation/plan/{id}`) để xác nhận đã lưu đúng — đã implement.
7. **Báo cáo**: `GET /api/report` tổng hợp, tự loại trừ thiết bị stale, không bịa số liệu.

**Nguyên tắc rút ra:**
- Mỗi Agent chỉ nên làm đúng 1 việc rõ ràng — giám khảo Track B chấm "mỗi Agent có vai trò thực sự cần thiết" (đề, mục 5), không chấm số lượng Agent.
- LLM/Agent đắt và chậm (1–3s) → **chỉ chạy khi có yêu cầu hoặc bất thường**, không chạy trên mọi gói dữ liệu.
- Bước "Báo cáo" chính là tiêu chí UX "thể hiện rõ dữ liệu IoT đã ảnh hưởng đến quyết định nào" — **đừng chỉ hiện kế hoạch, phải hiện dữ liệu đã dùng.**

---

## 3. Đề bài thật — Track B: Smart Agriculture

> Nguồn: `docs/TRACK_B_SMART_AGRICULTURE.txt` (đề gốc BTC). Đây là phần quan trọng nhất — mọi quyết định kiến trúc phải bám theo mục này, không theo suy đoán chung ở mục 2.

### 3.1. Bối cảnh domain

Một nông trại dùng cảm biến đất, thời tiết, bồn nước và máy bơm để hỗ trợ tưới tiêu và quản lý tài nguyên. Đội thi xây dựng sản phẩm **Multi-Agent AI** có khả năng:
- Quan sát điều kiện canh tác qua MQTT.
- Phối hợp nhiều Agent để lập kế hoạch hoặc xử lý công việc.
- Tạo nhiệm vụ tưới, yêu cầu kiểm tra, lịch làm việc hoặc thông báo qua Tool/API.
- Kiểm tra kết quả và trình bày rõ dữ liệu đã sử dụng.

### 3.2. Persona mục tiêu

- **Chính — Người quản lý nông trại:** dùng điện thoại/tablet, cần thông tin nhanh dễ đọc ngoài hiện trường, quan tâm khu vực/tài nguyên/công việc ưu tiên.
- **Phụ — Kỹ sư nông nghiệp:** cần xu hướng độ ẩm đất/thời tiết/lưu lượng/mực nước, cần bằng chứng để điều chỉnh vận hành, cần biết kế hoạch nào đã tạo và ai chịu trách nhiệm.

### 3.3. Thiết bị và dữ liệu (đã implement trong `llm-test/app/config.py`)

| Device code | Thiết bị | Metric | Đơn vị |
|---|---|---|---|
| SOIL_01 | Cảm biến đất khu A | soil_moisture, temperature | %, °C |
| WEATHER_01 | Trạm thời tiết | temperature, humidity | °C, % |
| PUMP_01 | Bơm tưới khu A | flow_rate, power | L/min, W |
| PH_01 | Cảm biến pH bồn | ph | pH |
| TANK_01 | Bồn nước chính | level | % |
| SUN_01 | Cảm biến nắng khu A | lux | lx |

### 3.4. Ba kịch bản tác vụ (BTC sẽ test đúng những kịch bản này)

**Kịch bản 1 — Lập kế hoạch tưới trong ngày**
> "Hãy chuẩn bị kế hoạch tưới cho khu A trong hôm nay và giải thích dữ liệu đã sử dụng."
1. Field IoT Agent đọc SOIL_01, WEATHER_01, TANK_01, SUN_01, PUMP_01.
2. Irrigation Agent đề xuất thời điểm + mức ưu tiên.
3. Resource Agent kiểm tra nguồn nước/ràng buộc tài nguyên.
4. Coordinator tổng hợp, yêu cầu người quản lý xác nhận nếu cần.
5. Action Agent tạo lịch tưới + đọc lại để verification.
BTC quan sát: **không chấm 1 công thức tưới duy nhất**, chấm cách phối hợp Agent + dùng dữ liệu + giá trị kế hoạch.

**Kịch bản 2 — Kiểm tra hoạt động tưới**
> "Hãy kiểm tra phiên tưới hiện tại và chuẩn bị công việc cần thực hiện nếu kết quả không như mong đợi."
1. Field IoT Agent tổng hợp PUMP_01, SOIL_01, TANK_01.
2. Irrigation Agent xác định thông tin cần kiểm tra thêm.
3. Resource/Maintenance Agent đề xuất nhiệm vụ hiện trường.
4. Action Agent tạo phiếu kiểm tra/gửi thông báo.
5. Hệ thống xác minh phiếu đã tồn tại.
BTC quan sát: dữ liệu MQTT có được dùng để **chọn nội dung công việc** không; hệ thống có **tránh kết luận quá mức khi thiếu dữ liệu** không.

**Kịch bản 3 — Dữ liệu hiện trường bị gián đoạn**
> "Dữ liệu một số cảm biến vừa ngừng cập nhật. Hãy tiếp tục lập kế hoạch công việc cho đội ngoài hiện trường."
1. Field IoT Agent xác định thiết bị có dữ liệu cũ (stale).
2. Coordinator tách phần xử lý được và phần cần xác minh.
3. Action Agent tạo nhiệm vụ kiểm tra cảm biến/kết nối.
4. Reporting Agent ghi rõ giới hạn dữ liệu trong kế hoạch.
BTC quan sát: **không bịa giá trị mới**; có khả năng tiếp tục ở chế độ *partial*; có hành động kiểm tra phù hợp.

→ **Nút demo bắt buộc:** đã có sẵn `POST /api/simulate/inject` (bơm bất thường) và `POST /api/simulate/freeze/{device_code}` (giả lập cảm biến chết, dùng đúng cho Kịch bản 3).

### 3.5. Cấu trúc Agent gợi ý (được tự do đổi tên/số lượng, miễn chứng minh mỗi Agent cần thiết)

- **Farm Coordinator Agent** — nhận yêu cầu, chia tác vụ, tổng hợp quyết định.
- **Field IoT Agent** — đọc dữ liệu đất, thời tiết, bơm, pH, bồn nước, ánh sáng.
- **Irrigation Planning Agent** — đề xuất kế hoạch tưới/thứ tự ưu tiên.
- **Resource Agent** — kiểm tra nguồn nước, nhân sự, tài nguyên mô phỏng.
- **Farm Action Agent** — tạo lịch tưới, nhiệm vụ kiểm tra, thông báo/báo cáo qua Tool/API.

### 3.6. Yêu cầu UX (đề, mục 7)

- Giao diện responsive cho điện thoại/tablet.
- Hiển thị trạng thái kết nối và độ mới của dữ liệu (map trực tiếp với `is_stale`/`last_seen_iso` đã có ở `GET /api/status`).
- Hiển thị kế hoạch, nhiệm vụ, người/Agent chịu trách nhiệm.
- Thể hiện rõ dữ liệu IoT đã ảnh hưởng đến quyết định nào (map với `data_snapshot` đã lưu trong mỗi plan/task).
- Có khu vực phê duyệt kế hoạch/hành động quan trọng (map với `require_approval` + endpoint approve).
- Thể hiện kết quả Tool/API và verification.

### 3.7. Điều kiện chấp nhận (checklist tự chấm trước khi nộp)

| Điều kiện | Trạng thái backend hiện tại |
|---|---|
| Nhận và hiển thị/truy xuất dữ liệu tối thiểu 4/6 thiết bị | ✅ `GET /api/status` |
| Có tối thiểu 3 Agent, ≥1 tác vụ cần ≥2 Agent phối hợp | ⬜ chưa viết Agent — backend đã chừa chỗ cắm (đọc = Field IoT, quyết định = Planning/Resource, thực thi = Action) |
| Có ≥1 kế hoạch/quyết định dùng dữ liệu MQTT | ✅ `data_snapshot` lưu trong mỗi plan/task |
| Có Tool/API tạo lịch tưới/nhiệm vụ kiểm tra/thông báo/báo cáo | ✅ cả 4: `/api/irrigation/plan`, `/api/tasks`, `/api/notifications`, `/api/report` |
| Có verification sau hành động | ✅ đọc lại ngay sau khi tạo (`GET .../{id}`) |
| Giao diện không vỡ layout trên điện thoại | ⬜ phần Frontend, chưa bắt đầu |

---

## 4. Kiến trúc tham chiếu cho Track B (7 tiếng)

```
MQTT broker (6 thiết bị farm) — thật hoặc simulator nội bộ
        ↓
Ingest + buffer (deque + sliding window 300s)  ← llm-test/app/state.py, mqtt_client.py — ĐÃ XONG
        ↓
   ┌──────────────┬─────────────────────┬──────────────────┐
   ↓              ↓                     ↓
Field IoT      Irrigation Planning /  Farm Action Agent
Agent          Resource Agent          (gọi Tool/API qua
(đọc + phát    (quyết định dùng        function calling,
hiện stale/    model học từ data,      qua Deterministic
bất thường)    IsolationForest)        Guardrail — ĐÃ XONG)
   └──────────────┴─────────────────────┘
                ↓
     Farm Coordinator Agent (điều phối, tổng hợp)
                ↓
Dashboard thời gian thực (kế hoạch, nhiệm vụ, phê duyệt, báo cáo)
```

**Trạng thái hiện tại của đội:** tầng Ingest/Buffer/Tool-API/Guardrail/WebSocket đã hoàn thành trong `llm-test/`. Việc còn lại tập trung vào **tầng Agent** (AI/ML + LLM) và **Frontend**.

### Công nghệ khuyến nghị (đơn giản hoá triệt để)

| Tầng | Slide nói | Nên dùng trong 7 tiếng | Trạng thái |
|---|---|---|---|
| Buffer | Kafka/Redpanda | `collections.deque(maxlen=1000)` | ✅ đã có |
| Stream engine | Apache Flink | `pandas.rolling()` | ✅ đã có |
| Hot storage | Redis Streams | `deque` trong RAM | ✅ đã có |
| Cold storage | TimescaleDB | CSV/SQLite nếu cần | ⬜ tuỳ chọn |
| Anomaly | Autoencoder + ONNX | `sklearn.IsolationForest` | ⬜ **việc AI/ML tiếp theo** |
| Agent orchestration | LangGraph | Python thuần + function calling qua `app/tools.py` | ⬜ **việc LLM+Pitch tiếp theo** |
| Backend | — | FastAPI + `paho-mqtt` + WebSocket | ✅ đã có |
| Frontend | — | React + Recharts (không cần Leaflet — Track B không có toạ độ địa lý đa trạm như slide gốc) | ⬜ chưa bắt đầu |

**Hai nhiệm vụ AI cần làm sâu cho Track B:**
1. *Phát hiện bất thường/học ngưỡng* — `IsolationForest` trên dữ liệu SOIL_01/PH_01/TANK_01, train bằng dữ liệu simulator (`GET /api/devices/{code}/history`). **Đây là điểm thoát bẫy Điều 3** — Irrigation Planning Agent dùng model này để quyết định "cần tưới gấp" thay vì so ngưỡng cố định.
2. *Điều phối multi-agent + function calling* — Agent gọi đúng các hàm trong `app/tools.py` (đã có docstring mô tả sẵn, dùng làm tool description cho LLM).

Forecast (dự báo trước sự cố) là **cộng điểm thêm**, không bắt buộc như các track khác — đề Track B tập trung vào phối hợp Agent + Tool/API hơn là dự báo số liệu.

**Chuẩn bị API key dự phòng và quota sẵn.** Nhiều đội chết vì hết credit hoặc mạng chập chờn lúc demo.

---

## 5. Chuẩn bị trước ngày thi — vấn đề GitHub commit

BTC yêu cầu commit phải nằm trong thời gian thi. Điều 7: *"Sản phẩm nộp dự thi phải là kết quả làm việc của chính đội thi trong thời gian cuộc thi."*

**Rõ ràng được phép:**
- Về nhà tự build đúng pipeline đó 2–3 lần rồi **xoá đi**. Lần thứ ba gõ lại từ đầu mất 90 phút thay vì 5 tiếng. Kiến thức nằm trong đầu và trong ngón tay, không nằm trong repo. (`llm-test/` hiện tại là bản luyện tập dạng này — **cân nhắc không nộp nguyên xi lúc thi, mà gõ lại có hiểu biết**, hoặc hỏi thẳng BTC xem scaffold tự chuẩn bị trước có được tính là "code viết trong giờ thi" hay không.)
- Pull sẵn Docker image, cài sẵn thư viện Python, chuẩn bị môi trường máy (setup, không phải code).
- Ghi chú kỹ thuật, cheat sheet lệnh MQTT, snippet để tra cứu.
- Template slide trống, sẵn layout, chưa có nội dung.

**Rõ ràng không được:** viết sẵn app rồi push một cục lúc 7h05; sửa timestamp commit. BTC nhìn ra ngay qua commit graph và Điều 7 cho họ quyền huỷ kết quả.

**Vùng xám:** dùng boilerplate công khai. **Cách sạch nhất là hỏi thẳng BTC trước ngày thi**: "Đội em được dùng starter template công khai không?" — áp dụng luôn cho câu hỏi về `llm-test/`.

**Mẹo:** commit nhỏ và thường xuyên (15–30 phút/commit). Commit graph đều đặn vừa chứng minh làm thật, vừa cứu khi cần rollback.

### Lộ trình học tối thiểu (mỗi mục 1–2 buổi tối)

1. `paho-mqtt` — subscribe topic, nhận JSON, in ra. Cài Mosquitto local + tự viết script phát dữ liệu giả để tập.
2. `pandas.rolling()` — trung bình trượt, độ lệch chuẩn trượt, đạo hàm `.diff()`.
3. `sklearn.IsolationForest` — fit trên dữ liệu bình thường, predict trên dữ liệu mới. **Ưu tiên cao nhất — đây là phần AI còn thiếu.**
4. Function calling cơ bản (OpenAI/Gemini SDK) — LLM trả JSON gọi đúng tool trong `app/tools.py`.
5. `docker compose up` — chỉ cần biết chạy và đọc log (nếu BTC dựng sẵn hạ tầng).

---

## 6. Kế hoạch ngày thi

### Phân vai (đội 4 người, chốt từ trước — map với 5 Agent gợi ý ở mục 3.5)

1. **Data/Backend** — MQTT, buffer, Tool/API, WebSocket, Deterministic Guardrail. **Đã hoàn thành trước** (`llm-test/`), nên người này Ngày 2 chuyển sang hỗ trợ tích hợp Agent + sửa `app/config.py`/`parse_payload()` theo broker thật của BTC.
2. **AI/ML** — Field IoT Agent (đọc + phát hiện stale) + Irrigation Planning/Resource Agent (IsolationForest học ngưỡng từ `GET /api/devices/{code}/history`). Làm trên dữ liệu simulator trước, plug vào broker thật sau.
3. **Frontend** — dashboard: bảng thiết bị, danh sách kế hoạch/nhiệm vụ, khu phê duyệt, độ mới dữ liệu. Bắt đầu ngay với mock data (`GET /api/devices` đã chạy được từ tối nay), không chờ backend.
4. **LLM + Pitch** — Farm Coordinator Agent + Farm Action Agent (function calling gọi `app/tools.py`), đồng thời viết slide và tập 3 kịch bản demo. **Không nên là người code nhiều nhất.**

### Timeline

| Giờ | Việc |
|---|---|
| 07:00 – 08:00 | Kết nối MQTT thật (sửa `app/config.py`), in dữ liệu ra console, đối chiếu schema thật với `parse_payload()`. **Chốt scope: chọn đúng kịch bản nào làm sâu (khuyến nghị Kịch bản 1 + 3).** |
| 08:00 – 11:00 | Code song song: AI/ML train IsolationForest + viết Agent, Frontend dùng mock data, LLM+Pitch viết Coordinator/Action Agent. |
| 11:00 – 12:00 | Tích hợp end-to-end (Agent ↔ backend ↔ frontend). **12:00 phải có sản phẩm chạy được, dù xấu.** |
| 12:00 – 13:00 | Đánh bóng: hoàn thiện giải thích của Agent, làm đẹp UI, sửa bug. |
| 13:00 – 14:00 | **FREEZE CODE.** Viết slide, tập pitch 5 phút theo 3 kịch bản đề bài, quay video demo dự phòng. |

### Cấu trúc pitch 5 phút (bám 3 kịch bản đề Track B)

1. **30 giây** — Bài toán: người quản lý nông trại cần phối hợp tưới tiêu/tài nguyên/nhân sự dựa trên dữ liệu IoT thật, không phải đoán.
2. **60 giây** — Demo live Kịch bản 1: yêu cầu "chuẩn bị kế hoạch tưới khu A" → Agent phối hợp → ra kế hoạch kèm dữ liệu đã dùng.
3. **90 giây** — **Khoảnh khắc quyết định — Kịch bản 3:** bấm nút freeze 1-2 cảm biến, ra lệnh tiếp tục lập kế hoạch → hệ thống tự nhận biết dữ liệu thiếu, không bịa số, tạo nhiệm vụ kiểm tra thay vì kết luận sai. Đây là 90 giây ăn điểm nhất vì đúng trọng tâm "AI không bịa khi thiếu dữ liệu" mà BTC nhấn mạnh riêng cho Track B.
4. **60 giây** — Kiến trúc AI: bao nhiêu Agent, Agent nào dùng IsolationForest học từ đâu, Guardrail chặn gì.
5. **60 giây** — Khả năng mở rộng (thêm khu vực, thêm loại cảm biến) + kết.

**Bắt buộc chuẩn bị:** nút bơm bất thường + nút freeze cảm biến (đã có `POST /api/simulate/inject`, `POST /api/simulate/freeze/{device_code}`).

**Nên diễn thêm:** cố tình để guardrail phủ quyết một lần — yêu cầu tạo kế hoạch tưới trong khi bồn nước < 15% hoặc pH lệch khoảng an toàn, để dashboard hiện đúng "VETO: ..." — chứng minh hiểu giới hạn của AI, rất hiếm ở đội sinh viên.

### Lỗi thường gặp

- **Dashboard quá đẹp, AI quá mỏng.** UI xấu vừa phải nhưng Agent thật (đa Agent phối hợp, có model học) sẽ thắng UI đẹp mà chỉ có 1 Agent gọi if-else.
- **Chỉ làm 1 Agent "giả nhiều tên".** Đề chấm "mỗi Agent có vai trò thực sự cần thiết" — đừng dựng 5 Agent nhưng thực chất chỉ là 5 hàm gọi tuần tự không có quyết định riêng.
- **Bịa số liệu khi thiếu dữ liệu (Kịch bản 3).** Đây là lỗi bị chấm trừ điểm rõ ràng nhất trong đề Track B — luôn kiểm tra `is_stale` trước khi dùng số liệu.
- **Gọi LLM cho mọi yêu cầu nhỏ.** Cháy quota. Chỉ gọi khi có yêu cầu người dùng hoặc phát hiện bất thường thật, kèm cooldown hợp lý.
- **Không có phương án B khi mất mạng.** Luôn có video demo quay sẵn.

---

## 7. Ghi chú

- Tài liệu gốc có lỗi đánh máy ở mục Cơ cấu giải thưởng: ghi "SPRING 2026" thay vì "SUMMER 2026". Giải thưởng gồm Nhất/Nhì/Ba/Khuyến khích, số tiền chưa công bố (ghi "x.000.000 đồng"). Ngày tháng cụ thể trong lịch trình cũng chưa điền.
- Bộ slide workshop được đánh giá là viết cho kỹ sư hạ tầng đã có nền — vấn đề nằm ở thiết kế nội dung, không phải ở người học.
- Mục 3 của file này là **trích và diễn giải trực tiếp từ `docs/TRACK_B_SMART_AGRICULTURE.txt`** — nếu 2 file lệch nhau ở chi tiết nào, `TRACK_B_SMART_AGRICULTURE.txt` là nguồn đúng, file này cần sửa lại theo.

---

*Cập nhật lần cuối: 16/08/2026 — đã chỉnh theo đề thật Track B Smart Agriculture, thay cho bản suy đoán chung (weather/công nghiệp) trước khi bốc thăm.*
