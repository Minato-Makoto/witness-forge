# UI Refactoring: Time & Token Metrics

## 📋 Summary

Refactored UI code để **tách biệt concerns**: di chuyển tất cả logic UI từ `main.py` vào `StreamRenderer`.

---

## ✅ Changes Made

### 1. **Enhanced `StreamRenderer` (src/witness_forge/ui/renderer.py)**

Thêm 3 methods mới:

#### `start_generation()`
```python
renderer.start_generation()
```
- Bắt đầu tracking time và reset token count
- Gọi trước khi streaming

#### `create_stream_callback(user_callback=None, style="green bold")`
```python
stream_cb = renderer.create_stream_callback(style="green")
```
- Tạo callback tự động đếm tokens
- Có thể wrap user's callback nếu cần
- Tự động print với style được chỉ định

#### `print_metrics(loop_info=None, loop_state=None, evolutions=None)`
```python
renderer.print_metrics(
    loop_info=state.get("loop_info"),
    loop_state=loop_state,
    evolutions=evolutions,
)
```
- In tất cả metrics (2 dòng)
- Dòng 1: Effective Temperature + loop params
- Dòng 2: `time=X.XXs tokens=XX temperature=X.XXX`

---

### 2. **Simplified `main.py`**

**Before** (56 lines of UI logic):
```python
# Track time and tokens
start_time = time.time()
token_count = 0

def stream_cb(token: str) -> None:
    nonlocal token_count
    console.print(token, style="green bold", end="")
    token_count += 1

# ... generation ...

elapsed = time.time() - start_time
tuned = loop_state.get("tuned", {}) or {}
# ... 20+ more lines of metrics formatting ...
```

**After** (7 lines):
```python
renderer.start_generation()
stream_cb = renderer.create_stream_callback(style="green bold")

# ... generation ...

renderer.print_metrics(loop_info, loop_state, evolutions)
```

---

## 📊 UI Output

```
You: Xin chào, bạn khỏe không?

Ark: Đây là câu hỏi chào hỏi thông thường.

Xin chào! Tôi sẵn sàng giúp bạn.

Effective Temperature: 0.742 (top_p=0.950, state=flow, k=0.0234, 
ε=0.1500, fast=+0.045, slow=-0.012, beta=0.85, reflex=0.678, 
evolution=base)
time=2.34s tokens=60 temperature=0.720
```

---

## 🎯 Benefits

1. **Separation of Concerns**: UI logic ở `renderer.py`, không còn trong `main.py`
2. **Reusability**: `StreamRenderer` có thể dùng ở bất kỳ đâu
3. **Cleaner Code**: `main.py` giảm từ ~56 lines → 7 lines
4. **Easier Testing**: UI logic tách biệt, dễ test
5. **Consistency**: Cả dual-brain và single-brain đều dùng cùng renderer

---

## 📝 Implementation Details

### Token Counting
```python
# Đếm số chunks từ streaming callback
self.token_count += 1
```

**Note**: Hiện tại đếm **chunks**, không phải exact tokens. Mỗi chunk có thể là 1+ tokens.

Để đếm exact tokens, cần:
```python
token_count = len(tokenizer.encode(full_text))
```

### Time Tracking
```python
self.generation_start_time = time.time()
# ... generation ...
elapsed = time.time() - self.generation_start_time
```

---

## 🔧 Usage Example

```python
from witness_forge.ui.renderer import StreamRenderer

renderer = StreamRenderer(console)

# Start generation
renderer.start_generation()

# Create callback with auto token counting
stream_cb = renderer.create_stream_callback(style="green")

# Use callback in generation
agent.step(text, stream=stream_cb)

# Print metrics
renderer.print_metrics(
    loop_info="Effective Temperature: ...",
    loop_state={"tuned": {"temperature": 0.72}},
    evolutions=["temperature=0.720"],
)
```

---

## ✅ Metrics Always Displayed

Dòng thứ 2 **LUÔN hiển thị**, không còn tình trạng ẩn/hiện:
- ✅ `time=X.XXs`
- ✅ `tokens=XX`
- ✅ `temperature=X.XXX`
- ✅ Evolution tuning (nếu có)

---

## 🚀 Next Steps (Optional)

1. **Exact token counting**: Dùng `tokenizer.encode()` thay vì đếm chunks
2. **Tokens/sec metric**: Thêm `tok/s` vào output
3. **Formatter abstraction**: Tách metrics formatting thành pluggable formatters
4. **Config-driven display**: Allow user config metrics display format
