# HACKATHON_CONTEXT.md

> **Mục đích của file này**
> Đây là bản tổng hợp toàn bộ bối cảnh và chiến lược cho cuộc thi SEAL Hackathon Summer 2026.
> Dán file này vào đầu một cuộc trò chuyện mới để trợ lý AI nắm được ngay bối cảnh mà không cần giải thích lại.
>
> **Người dùng:** sinh viên CNTT chuẩn bị dự thi, xuất phát điểm chưa có nền về IoT streaming / stream processing.
> **Ngôn ngữ trao đổi:** tiếng Việt.
> **Đã loại trừ:** phần thảo luận về kiến trúc multi-agent cho track logistics (chỉ là ví dụ minh hoạ, không thuộc bối cảnh chung).

---

## 1. Thông tin cuộc thi

**Tên:** SEAL Hackathon Summer 2026 (Software Engineering Agile League)
**Đơn vị tổ chức:** Trường Đại học FPT cơ sở TP.HCM
**Đối tượng:** Sinh viên CNTT tại ĐH FPT HCM và các trường ĐH khác tại TP.HCM (theo thư mời). Sinh viên đã tốt nghiệp không được tham gia.

**Chủ đề:** *"AI-Driven Smart Operations: Turning Real-Time IoT Data into Intelligent Actions"*

**Hệ thống Hackathon:** SEAL tổ chức 3 kỳ mỗi năm — Emerging Technologies, Product & User Experience, SDLC & Professional Working. Có 3 loại bảng xếp hạng: Chapter (cộng dồn cả năm), Team (từng kỳ, không cộng dồn), Cá nhân (cộng dồn cả năm).

### Cấu trúc thi đấu

- **3 Track**, mỗi Track là một lĩnh vực vận hành thông minh khác nhau.
- **Chủ đề cụ thể của từng Track được giữ bí mật**, chỉ công bố qua bốc thăm tại buổi gặp mặt Ngày 1.
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

Dashboard đẹp + `if (temp > 80) alert()` = mất phần lớn 60% điểm (30% "Hiệu quả ứng dụng AI" + 30% "Xử lý dữ liệu thời gian thực").
**Bắt buộc phải có model học ngưỡng từ dữ liệu, không hardcode con số.**

---

## 2. Nội dung Workshop đã được giải mã

Workshop có 5 phần (Smart Operations Evolution, Real-Time Streaming Pipeline, AI Engine & Agentic Workflows, End-to-End Reference Architecture, Live Q&A). Người dùng phản hồi là diễn giả chỉ đọc slide và khó hiểu — slide viết cho kỹ sư hạ tầng đã có nền, không phải cho người học từ đầu.

**Đánh giá tổng quát: khoảng 80% nội dung slide là kiến trúc production cấp doanh nghiệp, KHÔNG dùng được trong 7 tiếng. Nhưng cần hiểu để nói đúng ngôn ngữ với giám khảo.**

### 2.1. Khung tư tưởng — 3 đời của Operational Monitoring

Đây là khung xuyên suốt cuộc thi và cũng là bố cục pitch:

1. **Passive Monitoring** ("Chuyện gì đã xảy ra?") — có dashboard, người ngồi nhìn 24/7. Độ trễ phát hiện sự cố rất cao.
2. **Reactive Alerting** ("Có đang hỏng không?") — luật IF-THEN với ngưỡng tĩnh. Vấn đề: báo động giả liên tục (alert fatigue) và **không bắt được suy thoái từ từ**.
3. **AI-Driven Smart Ops** ("Tại sao và sửa thế nào?") — phát hiện bất thường liên tục, phân tích nguyên nhân gốc tự động, vòng lặp khép kín.

→ Điều 3 chính là lệnh cấm nộp sản phẩm đời 2.

### 2.2. Từ điển thuật ngữ

**Telemetry** — số liệu cảm biến gửi về liên tục.

**MQTT (cổng 1883, TCP)** — giao thức pub/sub cho IoT. Cảm biến publish lên *topic*, ai cần thì subscribe, ở giữa có *broker* làm bưu điện. QoS 0 = có thể mất; QoS 1 = đảm bảo tới nhưng có thể trùng (**khuyến nghị dùng**); QoS 2 = đúng một lần, chậm. Thư viện: `paho-mqtt`.

**CoAP (cổng 5683, UDP)** — tương tự nhưng nhẹ hơn, cho cảm biến chạy pin. Gần như không cần đụng tới.

**Kafka / Redpanda (cổng 9092)** — băng chuyền có đệm giữa nguồn và bộ xử lý. Ghi dữ liệu xuống sổ cái append-only, đọc lại được khi crash. Redpanda = Kafka viết bằng C++, nhẹ hơn, không cần JVM, API y hệt. *Partition key = station_id* để giữ đúng thứ tự thời gian của từng trạm.

**Windowing** — cắt dòng dữ liệu vô tận thành khúc để tính toán:
- *Tumbling window (60s)*: các khúc không chồng lấn. Dùng tính thống kê nền.
- *Sliding window (300s, trượt 60s)*: các cửa sổ chồng lấn 80%. Dùng bắt **xu hướng và độ dốc**.
- Ví dụ quyết định: áp suất 1005 hPa là bình thường, nhưng 1005 mà **đang giảm 3 hPa/giờ** nghĩa là bão đang tới. Chỉ sliding window thấy được. Slide gọi là `Delta P / Delta t`.
- Trong pandas cả hai chỉ là `df.rolling()` với tham số khác nhau.

**Event-time vs Processing-time** — dữ liệu sinh lúc 9:00:08 nhưng tới nơi 9:00:12. **Luôn dùng timestamp cảm biến gắn trong payload**, không dùng giờ hệ thống.

**Watermark (5s)** — quy ước "chờ tối đa 5 giây rồi chốt sổ cửa sổ, ai tới trễ hơn cho ra luồng riêng (side-output)".

**Hot / Cold Storage:**
- *Redis Streams* — kho nóng trong RAM, <1ms, giữ ~1000 bản ghi gần nhất, cho AI đọc suy luận tức thời.
- *TimescaleDB / InfluxDB* — kho lạnh trên đĩa, giữ vô hạn, chậm hơn, để train model và xem lịch sử.

**Isolation Forest** — phát hiện bất thường **không cần nhãn**. Trực giác: chặt ngẫu nhiên không gian dữ liệu bằng các nhát cắt. Điểm bình thường nằm giữa đám đông cần nhiều nhát mới cô lập; điểm dị thường nằm chơ vơ chỉ cần vài nhát. Số nhát cắt = điểm bất thường. Chạy CPU, `sklearn.ensemble.IsolationForest`, `contamination=0.03`. **Đây là lựa chọn đúng cho 7 tiếng.**

**Autoencoder** — mạng neural bóp cổ chai, học nén rồi phục dựng. Reconstruction error cao = dữ liệu lạ. Mạnh hơn nhưng cần train + PyTorch. **Bỏ qua trong 7 tiếng.**

**FFT** — biến tín hiệu rung từ miền thời gian sang miền tần số. Chỉ cần nếu track có cảm biến rung tần số cao.

**SHAP** — sau khi model kêu "bất thường", SHAP trả lời "vì cảm biến nào", phân bổ phần trăm đóng góp cho từng biến (ví dụ: rung trục 78%, áp suất 14%, nhiệt độ 8%). `pip install shap`, chạy được ngay với model sklearn. **Rẻ và trông rất chuyên nghiệp — nên làm.**

**Causal DAG / Root Cause Analysis** — phân biệt nguyên nhân gốc với triệu chứng lan truyền. Ví dụ: Van A tắc → áp suất B tăng → nhiệt độ C tăng. Ba cảnh báo nổ nhưng chỉ cần sửa van A. **Không cần thư viện Bayesian** — chỉ cần một dict Python mô tả quan hệ nhân quả của domain + so sánh cảnh báo nào nổ trước.

**Function Calling** — mô tả cho LLM danh sách "công cụ" nó được gọi; LLM trả về tên hàm + tham số thay vì văn xuôi. Đó là cách LLM "hành động".

**SOP (Standard Operating Procedure)** — quy trình vận hành chuẩn. Trong sản phẩm chỉ là file JSON/markdown kiểu "nếu X thì làm Y", nhét vào prompt làm ngữ cảnh.

**PLC** — máy tính công nghiệp điều khiển thiết bị. Trong demo chỉ cần publish ngược lại một MQTT topic để giả lập.

**Deterministic Guardrail** — tầng luật cứng **bằng Python thuần** chặn giữa LLM và thiết bị. LLM có thể ảo giác, nên trước khi lệnh thi hành, một hàm kiểm tra ví dụ: *"nếu lệnh là đóng van chính mà áp suất > 100 bar thì từ chối"*. LLM không có quyền phủ quyết tầng này. Chỉ ~20 dòng code nhưng **rất ăn điểm khi nói trong pitch**.

**Dual-Mode Execution:**
- *Fully Autonomous* — lệnh khẩn cấp dưới 1 giây, tự động hoàn toàn.
- *Human-in-the-loop* — thao tác không đảo ngược được thì hiện dialog Approve/Reject.
→ Làm cả hai, demo cả hai. Mất ~30 phút, ăn điểm trải nghiệm người dùng.

### 2.3. Trình tự xử lý chuẩn (sequence diagram của BTC)

1. Thiết bị IoT bắn telemetry → Edge Detector
2. Edge Detector tự tính anomaly score (Isolation Forest), so ngưỡng
3. **Chỉ khi vượt ngưỡng** mới emit anomaly event vào Event Stream (kèm `machine_id`, metrics)
4. Event Stream trigger AI Decision Agent chạy Root-Cause Analysis
5. Agent tự đánh giá rủi ro + tra cứu SOP
6. Agent gửi lệnh khẩn cấp xuống PLC
7. PLC thực thi xuống thiết bị (closed-loop hoàn tất)
8. Agent cập nhật Incident Log và **giải thích quyết định** lên Dashboard

**Nguyên tắc thiết kế rút ra từ vị trí bước 2 và 5:**
- Phát hiện bất thường rẻ và nhanh (<1ms) → chạy trên **mọi** điểm dữ liệu.
- LLM đắt và chậm (1–3s) → **chỉ chạy khi có bất thường**.
- Gọi LLM cho từng gói dữ liệu = cháy quota + dashboard đứng hình. Cả buổi demo có thể chỉ cần 3–5 lần gọi LLM.
- Bước 8 ("giải thích quyết định") chính là tiêu chí 30% của vòng chung kết. **Đừng chỉ hiện cảnh báo, phải hiện lý do.**

---

## 3. Stack mà BTC nhiều khả năng cung cấp sẵn

Slide "Real-Time Edge Weather Analytics Blueprint" và "IoT & AI Smart Operations Platform" chi tiết đến mức gần như chắc chắn là môi trường BTC dựng sẵn (100% containerized Docker Compose):

| Container | Cổng | Vai trò |
|---|---|---|
| `weather-simulator` | — | Python asyncio, giả lập 5 trạm thời tiết đồng thời |
| `weather-mqtt-bridge` | 1883 TCP | Broker MQTT bọc sensor stream thành JSON |
| `weather-coap-gateway` | 5683 UDP | Gateway low-power |
| `weather-redpanda` | 9092 TCP | Event broker |
| `redpanda-console` | 8088 Web | UI quan sát queue |
| `weather-stream-engine` | — | **Phần đội thi phải viết** |
| `weather-web-dashboard` | 8000 Web | **Phần đội thi phải viết** |

**Cảm biến:** Temperature, Humidity, Wind Speed, Pressure.

**4 topic Kafka = bản đồ module của sản phẩm:**
- `weather-raw` — dữ liệu thô
- `weather-aggregated` — đã qua windowing (trung bình, độ lệch, độ dốc)
- `weather-alerts` — sự kiện bất thường
- `weather-forecasts` — kết quả dự báo

→ Bốn tên này ngụ ý BTC mong đợi **cả anomaly detection lẫn forecasting**, không phải chọn một. Cũng là cách chia việc tự nhiên cho 4 người.

**Thông số đã chốt sẵn:** watermark 5s, tumbling window 60s, sliding window 300s. Cứ dùng đúng.

**LLM:** slide vẽ cả Gemini 2.5 Flash và GPT-4o. **Chọn một** — Gemini Flash rẻ hơn, nhanh hơn, free tier rộng hơn.

**Frontend gợi ý:** FastAPI + WebSocket `/ws/telemetry`, Leaflet GIS Map, Chart.js realtime.

> **Hệ quả quan trọng:** đừng học cách *dựng* Kafka, hãy học cách *đọc từ* Kafka và MQTT. Bốn container bên trái là quà tặng; chỉ cần viết hai container bên phải.

### Cơ hội ăn điểm cao nhất: Leaflet GIS Map

5 trạm ở vị trí địa lý khác nhau. Bản đồ với 5 chấm, chấm nào bất thường thì đỏ lên, click vào hiện chẩn đoán AI — mất ~45 phút code nhưng trên màn chiếu ăn đứt mọi biểu đồ đường. Trong 5 phút pitch, giám khảo nhớ **hình ảnh**, không nhớ kiến trúc.

Nhiều trạm còn cho phép **so sánh chéo**: trạm 3 báo áp suất giảm mạnh trong khi 4 trạm còn lại bình thường → hoặc cảm biến hỏng, hoặc thời tiết cực đoan cục bộ. Phân biệt được hai trường hợp đó chính là "chẩn đoán nguyên nhân gốc", tự nhiên hơn nhiều so với vẽ causal DAG.

---

## 4. Kiến trúc tham chiếu cho 7 tiếng

```
Nguồn dữ liệu cảm biến (MQTT broker của BTC)
        ↓
Ingest + buffer (sliding window, chuẩn hoá)
        ↓
   ┌────────────┬──────────────┬──────────────────┐
   ↓            ↓              ↓
Phát hiện    Dự báo        Chẩn đoán + đề xuất
bất thường   rủi ro        (LLM giải thích)
(model học   (cảnh báo
từ stream)   trước sự cố)
   └────────────┴──────────────┘
        ↓
Dashboard thời gian thực (cảnh báo + hành động đề xuất)
```

Khung này **không phụ thuộc đề bài**. Track là nhà máy, nông nghiệp hay tòa nhà thì chỉ đổi tên biến cảm biến và câu prompt cho LLM.

### Công nghệ khuyến nghị (đơn giản hoá triệt để)

| Tầng | Slide nói | Nên dùng trong 7 tiếng |
|---|---|---|
| Buffer | Kafka / Redpanda | `collections.deque(maxlen=1000)` nếu BTC không dựng sẵn |
| Stream engine | Apache Flink | `pandas.rolling()` trong Python |
| Hot storage | Redis Streams | `deque` trong RAM |
| Cold storage | TimescaleDB | file CSV hoặc SQLite |
| Anomaly | Autoencoder + ONNX | `sklearn.IsolationForest` |
| Forecast | — | lag features + `GradientBoostingRegressor` |
| Explain | SHAP + Causal DAG | SHAP (dễ) + dict quan hệ nhân quả |
| Agent | LangGraph | Python thuần + function calling |
| Backend | — | FastAPI + `paho-mqtt` + WebSocket |
| Frontend | — | React + Recharts + Leaflet |

**Ba nhiệm vụ AI, chọn 2 làm sâu (đề chỉ yêu cầu "ít nhất một"):**
1. *Phát hiện bất thường* — `river` (ML streaming, học online) hoặc `IsolationForest`, train bằng 5–10 phút dữ liệu đầu tiên của cuộc thi. **Model tự học ngưỡng từ dữ liệu — đây là điểm thoát bẫy Điều 3.**
2. *Dự báo* — tạo lag features (giá trị 1, 5, 10 phút trước) → `GradientBoostingRegressor` dự đoán 10 phút tới. Cho phép nói "cảnh báo trước 10 phút", rất ăn điểm.
3. *Chẩn đoán + đề xuất* — gọi Gemini API với context gồm chỉ số hiện tại, anomaly score, lịch sử gần, mô tả domain. Yêu cầu trả JSON: `{nguyên_nhân, mức_độ, hành_động_đề_xuất}`. Build nhanh nhất, ấn tượng nhất khi demo.

**Chuẩn bị API key dự phòng và quota sẵn.** Nhiều đội chết vì hết credit hoặc mạng chập chờn lúc demo.

---

## 5. Chuẩn bị trước ngày thi — vấn đề GitHub commit

BTC yêu cầu commit phải nằm trong thời gian thi. Điều 7: *"Sản phẩm nộp dự thi phải là kết quả làm việc của chính đội thi trong thời gian cuộc thi."*

**Rõ ràng được phép:**
- Về nhà tự build đúng pipeline đó 2–3 lần rồi **xoá đi**. Lần thứ ba gõ lại từ đầu mất 90 phút thay vì 5 tiếng. Kiến thức nằm trong đầu và trong ngón tay, không nằm trong repo.
- Pull sẵn Docker image, cài sẵn thư viện Python, chuẩn bị môi trường máy (setup, không phải code).
- Ghi chú kỹ thuật, cheat sheet lệnh MQTT, snippet để tra cứu.
- Template slide trống, sẵn layout, chưa có nội dung.

**Rõ ràng không được:** viết sẵn app rồi push một cục lúc 7h05; sửa timestamp commit. BTC nhìn ra ngay qua commit graph và Điều 7 cho họ quyền huỷ kết quả.

**Vùng xám:** dùng boilerplate công khai. **Cách sạch nhất là hỏi thẳng BTC trước ngày thi**: "Đội em được dùng starter template công khai không?"

**Mẹo:** commit nhỏ và thường xuyên (15–30 phút/commit). Commit graph đều đặn vừa chứng minh làm thật, vừa cứu khi cần rollback.

### Lộ trình học tối thiểu (mỗi mục 1–2 buổi tối)

1. `paho-mqtt` — subscribe topic, nhận JSON, in ra. Cài Mosquitto local + tự viết script phát dữ liệu giả để tập.
2. `pandas.rolling()` — trung bình trượt, độ lệch chuẩn trượt, đạo hàm `.diff()`. Hiểu `Delta P / Delta t`.
3. `sklearn.IsolationForest` — fit trên dữ liệu bình thường, predict trên dữ liệu mới.
4. `FastAPI` + WebSocket — đẩy dữ liệu realtime lên trình duyệt.
5. `docker compose up` — chỉ cần biết chạy và đọc log.
6. Gọi Gemini API trả về JSON có cấu trúc.

Sáu mục này là 90% những gì cần. Flink, ONNX, TimescaleDB, autoencoder, watermarking nâng cao chỉ là **từ vựng để nói trong pitch**, không phải thứ để xây.

---

## 6. Kế hoạch ngày thi

### Phân vai (đội 4 người, chốt từ trước)

1. **Data/Backend** — MQTT, buffer, WebSocket. Phải xong trong 90 phút đầu, nếu không cả đội đứng hình.
2. **AI/ML** — model bất thường + dự báo. Làm trên dữ liệu giả trước, plug vào stream thật sau.
3. **Frontend** — dashboard. Bắt đầu ngay với mock data, không chờ backend.
4. **LLM + Pitch** — tầng chẩn đoán, đồng thời viết slide và tập thuyết trình. **Không nên là người code nhiều nhất.**

### Timeline

| Giờ | Việc |
|---|---|
| 07:00 – 08:00 | Kết nối MQTT thật, in dữ liệu ra console, hiểu schema. **Chốt scope: chọn đúng 3 tính năng, cắt hết phần còn lại.** |
| 08:00 – 11:00 | Code song song. Frontend dùng mock data. |
| 11:00 – 12:00 | Tích hợp end-to-end. **12:00 phải có sản phẩm chạy được, dù xấu.** |
| 12:00 – 13:00 | Đánh bóng: thêm LLM, làm đẹp UI, sửa bug. |
| 13:00 – 14:00 | **FREEZE CODE.** Viết slide, tập pitch 5 phút, quay video demo dự phòng. |

Cái freeze 1 tiếng nghe phí nhưng là thứ phân biệt đội vào chung kết với đội không vào. Tổ hợp "chạy ổn định + trình bày mạch lạc" mới là thứ giám khảo thực sự chấm.

### Cấu trúc pitch 5 phút

1. **30 giây** — Bài toán: "Trong domain này, khi X hỏng thì thiệt hại là Y."
2. **60 giây** — Demo live: dữ liệu đang chảy, dashboard đang cập nhật.
3. **90 giây** — **Khoảnh khắc quyết định:** bơm một sự cố vào stream, hệ thống tự phát hiện → tự giải thích nguyên nhân → tự đề xuất hành động. Đây là 90 giây ăn điểm nhất cả cuộc thi.
4. **60 giây** — Kiến trúc AI: model gì, học từ đâu, độ chính xác bao nhiêu. Có số liệu càng tốt.
5. **60 giây** — Khả năng mở rộng sang domain khác + kết.

**Bắt buộc chuẩn bị:** một nút bấm trong dashboard để **bơm dữ liệu bất thường vào stream theo ý muốn**. Đừng ngồi cầu nguyện dữ liệu tự bất thường đúng lúc demo.

**Nên diễn thêm:** cố tình cho guardrail phủ quyết một lần — bơm kịch bản cực đoan, để LLM chọn sai, guardrail chặn lại và hiện "VETO: vượt giới hạn vật lý cứng". Chứng minh bạn hiểu giới hạn của AI, rất hiếm ở đội sinh viên.

### Lỗi thường gặp

- **Dashboard quá đẹp, AI quá mỏng.** Đảo ngược ưu tiên: UI xấu vừa phải nhưng AI thật sẽ thắng UI đẹp mà chỉ có `if-else`.
- **Ôm cả 4 nhiệm vụ AI.** Làm 2 cái sâu tốt hơn 4 cái nửa vời.
- **Demo bằng dữ liệu tĩnh.** Tiêu chí đầu tiên là "xử lý dữ liệu thời gian thực" — phải cho thấy stream đang chảy thật.
- **Không có phương án B khi mất mạng.** Luôn có video demo quay sẵn và chế độ replay dữ liệu từ file local.
- **Gọi LLM cho mọi điểm dữ liệu.** Cháy quota, dashboard đứng hình. Chỉ gọi khi có anomaly, kèm cooldown ~60 giây cho cùng một nguồn.
- **Tự dựng Kafka/TimescaleDB.** Nếu BTC dựng sẵn thì dùng; nếu không thì bỏ luôn.

---

## 7. Ghi chú

- Tài liệu gốc có lỗi đánh máy ở mục Cơ cấu giải thưởng: ghi "SPRING 2026" thay vì "SUMMER 2026". Giải thưởng gồm Nhất/Nhì/Ba/Khuyến khích, số tiền chưa công bố (ghi "x.000.000 đồng"). Ngày tháng cụ thể trong lịch trình cũng chưa điền.
- Bộ slide workshop được đánh giá là viết cho kỹ sư hạ tầng đã có nền — vấn đề nằm ở thiết kế nội dung, không phải ở người học.

---

*Cập nhật lần cuối: 16/08/2026*
