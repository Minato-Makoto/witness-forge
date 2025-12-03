# Evolution System - Hướng Dẫn Chi Tiết

## Tổng Quan

**Evolution System** là cơ chế tự điều chỉnh của Witness Forge, cho phép model tự động tune các generation parameters dựa trên quality metrics (reflex score) mà không cần restart hoặc thay đổi file config.yaml.

### Triết Lý: Living AI Without DNA Mutation

```
config.yaml = DNA (immutable baseline)
    ↓
active_evolution.json = Epigenetic overlay (runtime tuning)
    ↓
Effective Parameters = DNA + Overlay
```

**Không giống các hệ thống khác:**
- ❌ Không rewrite config.yaml
- ❌ Không tạo hàng chục patch files
- ✅ 1 file patch duy nhất, update incremental
- ✅ Tự động freeze khi converge
- ✅ Manual reset khi cần

---

## Reflex Score - Chỉ Số Chất Lượng

### Công Thức Tính

```python
reflex_score = (
    0.25 * coherence        # Mạch lạc văn bản  
    + 0.20 * repetition     # Tránh lặp lại
    + 0.20 * relevance      # Liên quan câu hỏi
    + 0.20 * thematic       # Giữ chủ đề
    + 0.15 * persona        # Ổn định phong cách
)
```

**Thang đo:** 0.0 → 1.0 (càng cao càng tốt)

### Components Chi Tiết

#### 1. Coherence (Mạch lạc)
- **Measure:** Độ dài câu trung bình, số câu hoàn chỉnh
- **Formula:** `0.3 + 0.02 * avg_sentence_length`
- **Good:** 0.5+ (câu đủ dài, rõ ràng)
- **Bad:** <0.4 (câu ngắn, rời rạc)

#### 2. Repetition (Không lặp)
- **Measure:** Tỷ lệ unique bigrams
- **Formula:** `1.0 - (unique_bigrams / total_bigrams)`
- **Good:** 0.8+ (đa dạng cách diễn đạt)
- **Bad:** <0.5 (lặp lại nhiều từ/cụm)

#### 3. Relevance (Liên quan)
- **Measure:** Overlap keywords với user input
- **Formula:** `0.4 + 0.6 * (shared_words / user_words)`
- **Good:** 0.7+ (answer đúng trọng tâm)
- **Bad:** <0.5 (answer lạc đề)

#### 4. Thematic Alignment (Giữ topic)
- **Measure:** Keyword overlap + diversity
- **Formula:** `overlap + 0.2 * (1 - repetition)`
- **Good:** 0.6+ (nhất quán chủ đề)
- **Bad:** <0.4 (nhảy topic)

#### 5. Persona Stability (Ổn định style)
- **Measure:** Độ tương đồng độ dài với response trước
- **Formula:** `1.0 - abs(len_diff) / max(len_prev, len_curr)`
- **Good:** 0.7+ (phong cách ổn định)
- **Bad:** <0.5 (style thay đổi đột ngột)

### Thresholds

```yaml
evolution:
  tune_threshold: 0.45   # Dưới đây → bắt đầu tune
  sync_threshold: 0.60   # Trên đây → freeze patch
```

**Zones:**
- `< 0.45`: **Danger** - quality quá thấp, cần tune
- `0.45-0.60`: **Neutral** - chấp nhận được, monitoring
- `> 0.60`: **Good** - converged, freeze baseline

---

## Evolution Lifecycle

### Phase 1: Base State (No Patch)

```
config.yaml: temperature=0.7
active_evolution.json: không tồn tại
Effective temperature: 0.7
```

**Trigger:** Reflex score < 0.45

### Phase 2: Evolving

```yaml
# active_evolution.json
{
  "state": "evolving",
  "overrides": {
    "model.temperature": 0.65  # Turn 1: 0.7 - 0.05
  },
  "evolution_history": [
    {"turn": 1, "score": 0.42, "tuned": {"temperature": 0.65}}
  ]
}
```

**Mỗi turn với score < 0.45:**
- Temperature giảm thêm 0.05
- Frequency penalty tăng 0.05
- Update vào `overrides`

**Example progression:**
```
Turn 1: score=0.42 → temp: 0.7 → 0.65
Turn 2: score=0.44 → temp: 0.65 → 0.60
Turn 3: score=0.48 → temp: 0.60 → 0.55
Turn 4: score=0.58 → temp: 0.55 (no change, in neutral zone)
Turn 5: score=0.62 → FREEZE!
```

### Phase 3: Converged (Stable)

```yaml
# active_evolution.json
{
  "state": "stable",  # ← Marked frozen
  "converged_at": "2025-11-26T16:15:00",
  "overrides": {
    "model.temperature": 0.55  # Final evolved value
  }
}
```

**Behavior:**
- Patch file **CƯN TỒN TẠI** (không delete)
- Không update nữa (freeze)
- Effective temperature = 0.55 (new baseline)
- Nếu score xuống lại < 0.45 → resume tuning từ 0.55

### Manual Reset

```
/evolution reset
# → Delete active_evolution.json
# → Back to config.yaml baseline (0.7)
```

---

## Parameters Ảnh Hưởng

### 1. Temperature

**Vai trò:** Kiểm soát randomness trong sampling

**Ảnh hưởng:**
- **High (0.7-1.0):** 
  - ✅ Creative, diverse
  - ❌ Dễ ramble, lặp lại
  - ❌ Coherence thấp
- **Low (0.4-0.6):**
  - ✅ Focused, coherent
  - ✅ Ít lặp lại
  - ❌ Ít đa dạng

**Evolution behavior:**
```
reflex_score < 0.45 → temperature -= 0.05
(down to min 0.4)
```

### 2. Frequency Penalty

**Vai trò:** Phạt tokens xuất hiện nhiều lần

**Ảnh hưởng:**
- **High (0.3+):**
  - ✅ Tránh lặp từ
  - ❌ Có thể mất từ quan trọng
- **Low (0.1-0.2):**
  - ✅ Tự nhiên hơn
  - ❌ Dễ lặp

**Evolution behavior:**
```
reflex_score < 0.45 → frequency_penalty += 0.05
(up to max 2.0)
```

### 3. Presence Penalty

**Vai trò:** Khuyến khích topics mới

**Ảnh hưởng:**
- **High (0.5+):**
  - ✅ Đa dạng topics
  - ❌ Dễ lạc đề
- **Low (0.0-0.2):**
  - ✅ Giữ topic tốt
  - ❌ Có thể hạn hẹp

**Evolution behavior:**
```
thematic_alignment < 0.5 → presence_penalty += 0.1
```

---

## Monitoring & Debugging

### UI Display

**Format:**
```
Effective Temperature: 0.650 (base=0.7, top_p=0.877, state=drift, 
k=2.0041, ε=0.0130, fast=-0.078, slow=-0.063, beta=0.3, 
reflex=0.645, evolution=evolving)
```

**Fields:**
- `Effective Temperature`: Actual value sau khi tune
- `base`: Original từ config.yaml
- `reflex`: Current quality score (0-1)
- `evolution`: 
  - `base` - no patch active
  - `evolving` - tuning in progress
  - `stable` - converged, frozen

### Patch File Inspection

```bash
# View active evolution state
cat patches/active_evolution.json

# Fields quan trọng:
# - state: "evolving" | "stable"
# - current_reflex_score: latest score
# - overrides: current tuned values
# - evolution_history: turn-by-turn log
```

### Commands

```
/evolution status   # Show current state
/evolution reset    # Delete patch, back to base
/evolution freeze   # Manually mark as stable
```

---

## Troubleshooting

### Q: Evolution không trigger

**Kiểm tra:**
1. Reflex score có < 0.45 không?
   ```
   # Check UI output: reflex=0.xxx
   ```
2. Evolution enabled?
   ```yaml
   evolution:
     enabled: true
   ```
3. File log:
   ```
   # Nên thấy: [evolution] tuned: ...
   ```

### Q: Patch tạo nhưng không apply

**Debug:**
```python
python -c "
from witness_forge.config.overlay import ConfigOverlay
from witness_forge.config import ConfigManager
from pathlib import Path

base = ConfigManager('config.yaml').config
overlay = ConfigOverlay(base, Path('patches/active_evolution.json'))
merged = overlay.apply()

print(f'Base temp: {base.model.temperature}')
print(f'Effective temp: {merged.model.temperature}')
"
```

### Q: Temperature không giảm

**Nguyên nhân:**
- Patch đã ở state `stable` → không tune nữa
- Score không đủ thấp (>= 0.45)
  
**Fix:**
```
/evolution reset  # Force restart từ base
```

---

## Best Practices

### 1. Baseline Config

Set `config.yaml` với **conservative values:**
```yaml
model:
  temperature: 0.7      # Reasonable default
  frequency_penalty: 0.2
  presence_penalty: 0.0
```

Evolution sẽ tune xuống nếu cần.

### 2. Thresholds

```yaml
evolution:
  tune_threshold: 0.45   # Không quá thấp (0.3) → quá aggressive
  sync_threshold: 0.60   # Không quá cao (0.8) → khó converge
  incremental_step: 0.05 # Nhỏ = smooth, lớn = fast
```

### 3. Monitoring

Theo dõi `reflex` score trong UI:
- Trend giảm → cần kiểm tra prompt/input quality
- Fluctuate → normal (conversation dynamics)
- Stuck low (<0.4) → manual intervention

### 4. Reset Timing

Reset patch khi:
- Chuyển topic hoàn toàn khác
- Model behavior "stuck" ở tham số thấp
- Test baseline performance

---

## Comparison với Hệ Thống Khác

| Feature | Witness Forge Evolution | Traditional |
|---------|------------------------|-------------|
| Config mutation | ❌ Immutable | ✅ Rewrites |
| Patch files | 1 active | Dozens |
| Apply method | Runtime overlay | Restart required |
| Convergence | Auto-freeze | Manual |
| Rollback | 1 command | Complex |
| Audit trail | In patch history | Separate logs |

**Ưu điểm:**
- No restarts
- Clean audit trail
- Easy rollback
- True "living" without mutation

**Trade-offs:**
- Thêm 1 layer indirection (overlay)
- Cần hiểu lifecycle
- Manual reset khi cần

---

## Reference

**Files:**
- `patches/active_evolution.json` - Active overlay
- `patches/converged_*.json` - Archived snapshots
- `config.yaml` - Immutable baseline

**Config:**
```yaml
evolution:
  enabled: true
  tune_threshold: 0.45
  sync_threshold: 0.60
  incremental_step: 0.05
  max_history_turns: 50
```

**Code:**
- `src/witness_forge/agent/evolution.py` - Controller
- `src/witness_forge/agent/evaluator.py` - Reflex scoring
- `src/witness_forge/config/overlay.py` - Merge logic
