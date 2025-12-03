# Fix: Duplicate Temperature Display

## 🐛 Issue

UI hiển thị duplicate `temperature=`:
```
time=2.34s tokens=42 temperature=0.720 temperature=0.715
                      ^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^^
                      từ renderer       từ evolution
```

---

## 🔍 Root Cause

**2 nguồn thêm temperature:**

1. **StreamRenderer.print_metrics()** (line 129):
   ```python
   metrics_parts.append(f"temperature={current_temp:.3f}")
   ```
   → Luôn thêm temperature từ `loop_state`

2. **EvolutionController._update_active_patch()** (line 157):
   ```python
   parts.append(f"temperature={v:.3f}")
   return formatted  # "temperature=0.715"
   ```
   → Khi evolution tune temperature, cũng return `temperature=X.XXX`

**Kết quả:** Cả 2 đều thêm → bị duplicate!

---

## ✅ Solution

**Logic mới:**
- Check xem evolution messages có chứa `"temperature"` không
- Nếu **có** → dùng temperature từ evolution (giá trị mới sau tuning)
- Nếu **không** → thêm current temperature từ loop_state

**Code:**
```python
# Check if evolution messages contain temperature tuning
has_evolution_temp = False
if evolutions:
    for note in evolutions:
        if not note.strip().lower().endswith("(no diff)"):
            # Check if this evolution message contains temperature
            if "temperature" in note.lower():
                has_evolution_temp = True
            metrics_parts.append(note)

# Only add temperature if evolution didn't already include it
if not has_evolution_temp:
    metrics_parts.append(f"temperature={current_temp:.3f}")
```

---

## 📊 Expected Behavior

### Case 1: **Có evolution tuning**
```
time=2.34s tokens=42 temperature=0.715
                      ^^^^^^^^^^^^^^^^^
                      từ evolution (giá trị mới)
```

### Case 2: **Không có evolution tuning**
```
time=2.34s tokens=42 temperature=0.720
                      ^^^^^^^^^^^^^^^^^
                      từ loop_state (giá trị hiện tại)
```

---

## 🧪 Testing

Script: `scripts/test_duplicate_fix.py`

**Test cases:**
1. ✅ With evolution tuning → chỉ 1 temperature (từ evolution)
2. ✅ Without evolution tuning → chỉ 1 temperature (từ loop_state)

---

## 📝 Files Modified

- ✅ `src/witness_forge/ui/renderer.py` (line 126-144)
  - Added `has_evolution_temp` check
  - Conditionally append temperature

---

## 🎯 Result

**BEFORE:**
```
time=2.34s tokens=42 temperature=0.720 temperature=0.715
```

**AFTER:**
```
time=2.34s tokens=42 temperature=0.715
```

✅ No more duplicates!
