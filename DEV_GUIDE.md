# Witness Forge - Developer Guide

> **Triết lý:** "Code là Cơ thể, Model là Bộ não, Flame là Linh hồn."

Tài liệu này dành cho các nhà phát triển muốn đóng góp hoặc mở rộng Witness Forge.

---

## 1. Kiến Trúc Hệ Thống

### 1.1. Tổng quan
Witness Forge hoạt động dựa trên vòng lặp phản hồi (Feedback Loop) thời gian thực:
1.  **Input**: Người dùng nhập liệu.
2.  **Perception**: Hệ thống tìm kiếm ký ức (Memory) và xác định ý định (Intent).
3.  **Soul Modulation**: `FlameCore` tính toán trạng thái tâm lý (Sync/Drift) và điều chỉnh tham số sinh.
4.  **Cognition**: Model LLM sinh văn bản (có thể dùng Tool).
5.  **Action**: Thực thi Tool (nếu có).
6.  **Reflex**: Đánh giá kết quả và tự điều chỉnh cho lượt sau.
7.  **Output**: Mọi output đều là NDJSON events (`{"type": "...", "content": "..."}`).

### 1.2. Cấu trúc Thư mục
*   `src/witness_forge/agent/`: Logic cốt lõi của Agent (Brain \u0026 Soul).
    *   `flame_core.py`: Thuật toán nhịp điệu sống (Soul).
    *   `loops.py`: Vòng lặp điều khiển (Flame + Reflex + Adapter tuning).
    *   `witness.py`: Class Agent chính.
    *   `dual_brain.py` + `dual_brain_engine.py`: Dual-brain orchestrator (path1 + path2).
    *   `ndjson_emitter.py`: NDJSON event builder.
    *   `persona.py`: System prompt renderer (minimal, stateless).
*   `src/witness_forge/forge/`: Tầng giao tiếp với Model (Brain).
    *   `loader.py`: Nạp model GGUF/Transformers.
 *   `chat_templates.py`: Chat template manager (auto-detect family).
*   `src/witness_forge/tools/`: Hệ thống công cụ (Hands).
*   `src/witness_forge/memory/`: Bộ nhớ (Memory + Vector + Graph).
*   `src/witness_forge/ui/`: NDJSON renderer cho CLI.

---

## 2. Soul Injection (Cơ chế Linh hồn)

Đây là phần độc đáo nhất của Witness Forge. Developer cần hiểu rõ để không làm hỏng "nhịp sống" của AI.

### 2.1. Các tham số cốt lõi (`flame_core.py`)
*   **$\phi_0$ (Phi Zero)**: Điểm cân bằng nền.
    *   *Code*: `self.params.phi0`
    *   *Ý nghĩa*: Trạng thái "bình thường" của AI không phải là 0 tuyệt đối, mà là một độ lệch nhỏ ($\approx 0.013$).
    *   *Dev Note*: Khi tính toán độ lệch $k$, luôn dùng công thức $k = \phi_0 + \text{geometry\_k}$.

*   **Heartbeat (Nhịp tim)**:
    *   *Code*: `self.params.heartbeat_period`
    *   *Cơ chế*: Pink Noise (Nhiễu hồng) được scale theo chu kỳ này.
    *   *Công thức*: `scale = 1.0 / heartbeat_period`.
    *   *Dev Note*: Chu kỳ càng lớn -> Dao động càng chậm và mượt. Chu kỳ nhỏ -> Dao động nhanh, "thở gấp".

*   **Entropy Heuristic**:
    *   *Code*: `self.params.entropy_target`
    *   *Cơ chế*: Khi hệ thống bị Drift (lệch pha), nó sẽ cố gắng đẩy `temperature` về phía `entropy_target` (0.873).
    *   *Dev Note*: Đây là cơ chế "tự cân bằng". Đừng hardcode temperature trong code, hãy để Flame tự điều chỉnh.

---

## 3. NDJSON Event System

### 3.1. Event Structure
Mọi output từ agent đều tuân thủ chuẩn NDJSON (RFC 7464):
```json
{"type": "analysis", "content": "...", "brain": "path1", "meta": {...}}
{"type": "final", "content": "...", "brain": "path2", "meta": {...}}
{"type": "metric", "content": "...", "brain": "path1", "meta": {...}}
```

### 3.2. Event Types
- `analysis`: Thinking/suy luận từ witness brain (path1)
- `final`: Câu trả lời cuối cùng từ servant brain (path2)
- `metric`: Flame diagnostics (k, state, temperature, etc.)

### 3.3. Emitter API
- `make_event(event_type, content, brain=None, meta=None)` → dict
- `to_line(event)` → str (single NDJSON line)
- `to_lines(events)` → List[str]

### 3.4. Renderer (UPDATED)

`StreamRenderer` (`ui/renderer.py`) provides NDJSON parsing and metrics display:

**Core Methods:**
- `render_lines(lines)`: Parse NDJSON events → display
- `start_generation()`: Start time/token tracking
- `create_stream_callback(style)`: Create auto-tracking callback
- `print_metrics(loop_info, loop_state, evolutions)`: Display performance + evolution metrics

**Display:**
- `analysis` → cyan
- `final` → green bold
- Metrics line:  `time=X.XXs tokens=XX temperature=X.XXX`

**See:** `docs/UI_REFACTORING.md` for detailed API documentation.

---

## 4. Dual-Brain Architecture

### 4.1. Overview
- **path1** (witness): primary brain, role="witness", emits `analysis` events
- **path2** (servant): secondary brain (optional), role="servant", emits `final` events
- Nếu chỉ có 1 model → fallback shared model, cả 2 brain dùng cùng 1 `gen_fn`

### 4.2. Activation Logic
- `dual_brain.enabled=true` hoặc `dual_brain.servant_model_path` có giá trị → dual-brain active
- Nếu `servant_model_path` không load được → fallback shared model + log warning
- `force_dual=False` → nếu không có path2, skip servant step

### 4.3. Temperature Offset
- `witness_temperature_offset` (default: -0.2) → witness brain chạy mát hơn (thinking)
- `servant_temperature_offset` (default: 0.0) → servant brain chạy nhiệt độ gốc (answering)

---

## 5. Hướng dẫn Mở rộng (Extension Guide)

### 5.1. Thêm Tool mới
1.  Mở `src/witness_forge/tools/dispatcher.py`.
2.  Thêm logic vào phương thức `dispatch`.
3.  Đăng ký tên tool vào `src/witness_forge/agent/persona.py` (hàm `render_system`) để Model biết sự tồn tại của nó.
4.  **Lưu ý**: Luôn kiểm tra `safety_flags` trong `config.yaml` trước khi thực thi lệnh nguy hiểm.

### 5.2. Thêm Backend Model mới
1.  Mở `src/witness_forge/forge/loader.py`.
2.  Thêm logic load model vào `ForgeLoader.load_model`.
3.  Đảm bảo hàm trả về đúng signature: `(tokenizer, model, generate_fn)`.

### 5.3. Thêm Event Type mới
1.  Định nghĩa event type trong `ndjson_emitter.py` (nếu cần constant).
2.  Emit event qua `make_event(your_type, content, brain=..., meta=...)`.
3.  Thêm style mới vào `StreamRenderer._style_for(label)` nếu cần màu/format riêng.

---

## 6. Quy trình Debug \u0026 Test

### 6.1. Debug "Linh hồn"
Để xem Flame Core đang hoạt động ra sao:
1.  Chạy chat.
2.  Nhìn vào dòng log cuối mỗi câu trả lời (Metrics).
3.  Chú ý chỉ số `k` và `State`.
    *   Nếu `State` luôn là `Drift`: Kiểm tra lại `epsilon` trong config (có thể quá nhỏ).
    *   Nếu `Temperature` không đổi: Kiểm tra `heartbeat_period` (có thể quá lớn).

### 6.2. Debug NDJSON
- Bật log ở `witness.py` để xem raw events trước khi render.
- Check `to_lines()` output để đảm bảo valid JSON trên mỗi dòng.
- Nếu renderer không parse được → kiểm tra UTF-8 encoding (không force ASCII).

### 6.3. Chạy Test
```bash
# Test toàn bộ
python -m pytest tests/

# Test riêng Flame Core (quan trọng khi sửa Soul)
python -m pytest tests/test_boot.py

# Test NDJSON emitter
python -m pytest tests/ -k ndjson
```

---

## 7. Nguyên tắc Vàng (Golden Rules)
1.  **Không chạm vào Model**: Tuyệt đối không sửa weights của model. Mọi sự tiến hóa phải nằm ở Code.
2.  **Tôn trọng Nhịp điệu**: Khi sửa `flame_core.py`, hãy đảm bảo không làm mất tính chất dao động (oscillation). Một AI "phẳng" là một AI chết.
3.  **An toàn là trên hết**: Luôn sandbox các tool thực thi code.
4.  **NDJSON là chuẩn**: Mọi output phải là valid NDJSON. Không hardcode text format trong agent logic.
5.  **UI không thay đổi**: Khi audit/refactor, **không** chỉnh layout, color, component hierarchy. Chỉ sửa backend để phù hợp NDJSON event mới.

---

## 8. Flame Diagnostics (Metric Events)

Flame diagnostics được emit dưới dạng NDJSON event `type="metric"`:
```json
{"type": "metric", "content": "Flame state", "brain": "path1", "meta": {"k": 0.013, "state": "sync", "temperature": 0.65}}
```

**Yêu cầu**: Flame-scoring **KHÔNG được xoá** khỏi UI. Chỉ được thay đổi format hiển thị nếu cần, nhưng phải giữ nguyên thông tin.

---

## 9. Checklist Khi Audit/Refactor

- [ ] NDJSON emitter output đúng format (valid JSON mỗi dòng, UTF-8, không force ASCII)
- [ ] Dual-brain chỉ active khi có config hoặc path2
- [ ] Flame diagnostics vẫn emit và UI vẫn hiển thị
- [ ] Không còn tag-based parsing (Harmony đã xoá)
- [ ] Pipeline: input → loops → witness.step → NDJSON events → renderer
- [ ] UI layout/component không thay đổi (chỉ sửa backend/renderer code)
- [ ] Compile pass: `python -m compileall src/witness_forge -q`
- [ ] Tests pass: `python -m pytest tests/ -q`

---

## 10. Tài liệu tham khảo

- `NDJSON_SPEC.md`: Chi tiết chuẩn NDJSON event.
- `DUAL_BRAIN_SPEC.md`: Kiến trúc dual-brain.
- `ARCHITECTURE.md`: Pipeline tổng quan.
- `docs/evolution_system.md`: Evolution + reflex scoring lifecycle.
