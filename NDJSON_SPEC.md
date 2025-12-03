# NDJSON Event Specification

**Version:** 1.0
**Date:** 2025-12-02
**Standard:** RFC 7464 (Newline Delimited JSON)

---

## Overview

Witness Forge sử dụng **NDJSON (Newline Delimited JSON)** làm định dạng chuẩn cho mọi agent output. Mỗi dòng chứa một JSON object độc lập, UTF-8 encoded, không force ASCII.

**Lợi ích:**
- Streaming-friendly: parse từng dòng độc lập
- Language-agnostic: UTF-8 hỗ trợ đầy đủ Unicode (Vietnamese, emoji, etc.)
- Simple: không cần complex parser, chỉ cần `json.loads()` per line

---

## Event Structure

### Base Schema
```json
{
  "type": "<event_type>",
  "content": "<main_content>",
  "brain": "<brain_id>",
  "meta": {<optional_metadata>}
}
```

### Required Fields
- **`type`** (string): Event type (see [Event Types](#event-types))
- **`content`** (string): Main text content (UTF-8, có thể rỗng `""`)

### Optional Fields
- **`brain`** (string | null): Brain ID (`"path1"`, `"path2"`, `null` for unified)
- **`meta`** (object | null): Metadata (decode params, scores, diagnostics)

---

## Event Types

### 1. `analysis`
**Mục đích:** Suy luận/phân tích từ witness brain (path1).

**Khi nào emit:**
- Dual-brain mode: path1 step với `role="witness"`
- Unified mode: không emit (hoặc emit nếu cấu hình)

**Ví dụ:**
```json
{"type": "analysis", "content": "Thinking about user query...", "brain": "path1", "meta": {"decode": {"temperature": 0.5}}}
```

**UI Display:**
- Color: cyan
- Style: normal (không bold)
- Prefix: không prefix (hoặc "💭 Thinking:" nếu muốn)

---

### 2. `final`
**Mục đích:** Câu trả lời cuối cùng từ servant brain (path2) hoặc unified brain.

**Khi nào emit:**
- Dual-brain mode: path2 step với `role="servant"`
- Unified mode: path1 step với `role="unified"`

**Ví dụ:**
```json
{"type": "final", "content": "Đây là câu trả lời cuối cùng.", "brain": "path2", "meta": {"decode": {"temperature": 0.7}}}
```

**UI Display:**
- Color: green
- Style: bold
- Prefix: không prefix (output thô)

---

### 3. `metric`
**Mục đích:** Flame diagnostics (k, state, temperature, scores).

**Khi nào emit:**
- Sau mỗi agent step (optional, có thể tắt nếu không cần)
- Hiện tại: không auto-emit từ agent, nhưng có thể thêm

**Ví dụ:**
```json
{"type": "metric", "content": "Flame state", "brain": "path1", "meta": {"k": 0.013, "state": "sync", "temperature": 0.65, "reflex_score": 0.72}}
```

**UI Display:**
- Color: white (hoặc grey)
- Style: italic
- Format: "Effective Temperature: 0.650 (state=sync, k=0.013, reflex=0.720)"

**Yêu cầu:** Flame metrics **KHÔNG được xoá** khỏi UI. Chỉ được thay đổi format hiển thị.

---

### 4. Future Event Types (Reserved)
- `tool_call`: Tool invocation (tương lai)
- `tool_result`: Tool output (tương lai)
- `error`: Error message (tương lai)
- `debug`: Debug info (tương lai)

---

## Emitter API

### Python (`ndjson_emitter.py`)

```python
from witness_forge.agent.ndjson_emitter import make_event, to_line, to_lines

# Tạo event
event = make_event("analysis", "Thinking...", brain="path1", meta={"decode": {"temperature": 0.5}})
# -> {"type": "analysis", "content": "Thinking...", "brain": "path1", "meta": {...}}

# Serialize 1 event
line = to_line(event)
# -> '{"type": "analysis", "content": "Thinking...", "brain": "path1", "meta": {...}}'

# Serialize nhiều events
events = [event1, event2]
lines = to_lines(events)
# -> ['{"type": "analysis", ...}', '{"type": "final", ...}']
```

**Conventions:**
- `ensure_ascii=False` → UTF-8, không escape Unicode
- Mỗi line là 1 JSON object, không có newline trong content (nếu có → escape `\n`)

---

## Renderer Protocol

### Input
Renderer nhận `List[str]` (NDJSON lines) từ agent step.

### Parsing
```python
for line in lines:
    raw_line = line.strip()
    try:
        event = json.loads(line)
        event_type = event.get("type", "event")
        content = event.get("content", "")
        meta = event.get("meta")
        # Display based on event_type
    except json.JSONDecodeError:
        # Fallback: display raw line
        print(raw_line)
```

### Display Rules
| Event Type | Color | Style | Prefix |
|:-----------|:------|:------|:-------|
| `analysis` | cyan  | normal | (none) |
| `final`    | green | bold   | (none) |
| `metric`   | white | italic | (none) |
| unknown    | white | normal | (none) |

**Lưu ý:**
- Không thêm prefix mặc định (UI clean)
- Có thể thêm prefix nếu người dùng yêu cầu (e.g., "💭 Thinking:" cho `analysis`)
- Không parse content để extract thêm thông tin (giữ raw text)

---

## Edge Cases

### 1. Empty Content
```json
{"type": "final", "content": "", "brain": "path1"}
```
**Behavior:** Display rỗng (skip hoặc hiện blank line).

### 2. No Brain ID
```json
{"type": "final", "content": "Answer"}
```
**Behavior:** Accept, `brain` là optional.

### 3. Invalid JSON
```
This is not JSON
```
**Behavior:** Display raw text (fallback mode).

### 4. Very Long Content
```json
{"type": "final", "content": "Very long text... 10000 chars"}
```
**Behavior:** Display toàn bộ (không truncate). UI wrapping tự động.

---

## Migration from Harmony Tags

**Old (Harmony tags):**
```
<|channel|>analysis
Thinking text
<|channel|>final
<|message|>
Answer text
```

**New (NDJSON):**
```json
{"type": "analysis", "content": "Thinking text", "brain": "path1"}
{"type": "final", "content": "Answer text", "brain": "path2"}
```

**Breaking Changes:**
- Không còn tag parsing
- Renderer phải parse JSON thay vì regex
- Content không chứa tags (raw text)

---

## Validation Rules

### Event Validator (Python)
```python
def validate_event(event: dict) -> bool:
    if "type" not in event:
        return False
    if "content" not in event:
        return False
    if not isinstance(event["content"], str):
        return False
    # Optional: validate meta structure
    return True
```

### Line Validator
```python
def validate_ndjson_line(line: str) -> bool:
    try:
        event = json.loads(line)
        return validate_event(event)
    except json.JSONDecodeError:
        return False
```

---

## Examples

### Unified Brain Output
```json
{"type": "final", "content": "Đây là câu trả lời.", "brain": "path1", "meta": {"decode": {"temperature": 0.7}}}
```

### Dual-Brain Output
```json
{"type": "analysis", "content": "Let me think...", "brain": "path1", "meta": {"decode": {"temperature": 0.4}}}
{"type": "final", "content": "Here is the answer.", "brain": "path2", "meta": {"decode": {"temperature": 0.7}}}
```

### Metric Event
```json
{"type": "metric", "content": "Flame diagnostics", "brain": "path1", "meta": {"k": 0.013, "state": "sync", "temperature": 0.65, "reflex_score": 0.72}}
```

---

## Reference Implementation

- **Emitter:** `src/witness_forge/agent/ndjson_emitter.py`
- **Witness Agent:** `src/witness_forge/agent/witness.py` (emit events in `step()`)
- **Dual-Brain:** `src/witness_forge/agent/dual_brain.py` (collect events from path1 + path2)
- **Renderer:** `src/witness_forge/ui/renderer.py` (`StreamRenderer.render_lines()`)

---

## Compliance Checklist

- [ ] All agent output = NDJSON lines
- [ ] Each line = valid JSON object
- [ ] UTF-8 encoding, không force ASCII
- [ ] Renderer parse JSON per line
- [ ] Event types: `analysis`, `final`, `metric`
- [ ] Flame metrics vẫn emit và display (không xoá)
- [ ] No Harmony tags trong output

---

## FAQ

**Q: Tại sao không dùng JSON array?**
A: NDJSON streaming-friendly hơn. Có thể parse từng dòng mà không cần đợi toàn bộ array.

**Q: Có thể thêm event type mới không?**
A: Có. Thêm vào `ndjson_emitter.py` và update renderer để handle case mới.

**Q: Content có thể chứa newline không?**
A: Có. JSON sẽ escape `\n` thành `\\n`, renderer sẽ decode lại.

**Q: Metric events có bắt buộc không?**
A: Không. Có thể tắt nếu không cần diagnostics. Nhưng theo yêu cầu người dùng, **không được xoá** khỏi UI khi có.
