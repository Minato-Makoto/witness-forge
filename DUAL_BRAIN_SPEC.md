# Dual-Brain Architecture Specification

**Version:** 1.0
**Date:** 2025-12-02

---

## Overview

**Dual-Brain Architecture** là cơ chế cho phép Witness Forge chạy **2 models song song** (path1 + path2) để xử lý 1 user query:

- **path1 (Witness Brain)**: Suy luận/phân tích/thinking (role="witness")
- **path2 (Servant Brain)**: Trả lời cuối cùng (role="servant")

**Mục đích:**
- Tách biệt thinking vs answering
- Cho phép witness brain chạy mát hơn (temperature thấp → chính xác)
- Cho phép servant brain sáng tạo hơn (temperature cao → tự nhiên)

**Fallback:**
- Nếu chỉ có 1 model → fallback shared model (path1 = path2)
- Nếu path2 load fail → fallback shared model + log warning

---

## Configuration

### YAML Schema (`config.yaml`)
```yaml
dual_brain:
  enabled: false  # true to activate dual-brain mode
  mode: sequential  # sequential | parallel (future)
  servant_model_path: null  # path to secondary model (path2)
  witness_temperature_offset: -0.2  # witness runs cooler
  servant_temperature_offset: 0.0  # servant runs at base temp
```

### Activation Logic

| Config | Behavior |
|:-------|:---------|
| `enabled=false` + `servant_model_path=null` | Unified brain (1 model, role="unified") |
| `enabled=true` + `servant_model_path=null` | Fallback shared model (path1 = path2) + warning |
| `enabled=true` + `servant_model_path="/path/to/model"` | True dual-brain (path1 ≠ path2) |
| `enabled=false` + `servant_model_path="/path/to/model"` | Load path2 anyway (enabled auto-set to true) |

**Kết luận:** Nếu `enabled=true` **hoặc** `servant_model_path` có giá trị → dual-brain active.

---

## Architecture Components

### 1. `DualBrainEngine` (`agent/dual_brain_engine.py`)

**Responsibility:** Orchestrate path1 + path2 steps.

```python
class DualBrainEngine:
    def __init__(self, path1: WitnessAgent, path2: Optional[WitnessAgent] = None, *, force_dual: bool = False):
        self.path1 = path1  # always required
        self.path2 = path2  # optional
        self.force_dual = force_dual  # if True, run both even if path2 is None (fallback shared)

    def step(self, user_input: str, *, context_memory: Optional[List[str]] = None) -> Dict[str, Any]:
        # Step 1: path1 (witness) with role="witness"
        primary = self.path1.step(user_input, role="witness", context_memory=context_memory, return_events=True)
        events.extend(primary["events"])
        lines.extend(primary["lines"])
       
        # Step 2: path2 (servant) if dual_active
        if self.force_dual or self.path2 is not None:
            secondary_agent = self.path2 or self.path1  # fallback shared if path2 is None
            secondary = secondary_agent.step(user_input, role="servant", context_memory=context_memory, return_events=True)
            events.extend(secondary["events"])
            lines.extend(secondary["lines"])
        
        return {"events": events, "lines": lines, "loop_state": loop_state}
```

**Key Points:**
- `force_dual=True` → run both steps even if path2 is None (fallback shared)
- `force_dual=False` + `path2=None` → skip servant step (unified mode)

---

### 2. `DualBrain` (`agent/dual_brain.py`)

**Responsibility:** NDJSON wrapper for `DualBrainEngine`.

```python
class DualBrain(DualBrainEngine):
    def step(self, user_input: str, context: Optional[List[str]] = None) -> Dict[str, Any]:
        result = super().step(user_input, context_memory=context or [])
        if not result.get("lines"):
            result["lines"] = to_lines(result.get("events", []))  # ensure NDJSON lines
        return result
```

**Key Points:**
- Đảm bảo output luôn có `lines` (NDJSON format)
- Kế thừa logic orchestration từ `DualBrainEngine`

---

### 3. `WitnessAgent` (`agent/witness.py`)

**Responsibility:** Single-brain agent, emit NDJSON events.

```python
class WitnessAgent:
    def __init__(self, tokenizer, generate_fn, base_decode, loops, mem, retriever, *,
                 template_manager=None, tool_dispatcher=None, loop_observer=None,
                 role: str = "unified", brain_id: str = "path1", temperature_offset: float = 0.0):
        self.role = role
        self.brain_id = brain_id
        self.temperature_offset = temperature_offset
        # ...

    def step(self, user_text: str, *, role: Optional[str] = None, return_events: bool = False, ...):
        active_role = role or self.role or "unified"
        # ... generate response ...
        event_type = "analysis" if active_role == "witness" else "final"
        event = make_event(event_type, text, brain=self.brain_id, meta={"decode": gen})
        lines = to_lines([event])
        result = {"text": text, "events": [event], "lines": lines, "loop_state": loop_state}
        if return_events:
            return result
        return "\n".join(lines)
```

**Key Points:**
- `role` determines event type: `"witness"` → `"analysis"`, `"servant"` → `"final"`, `"unified"` → `"final"`
- `temperature_offset` applied trên decode params
- `brain_id` embed trong event (`"path1"` hoặc `"path2"`)

---

## Data Flow

### Unified Mode (1 model)
```
User Input
    ↓
WitnessAgent.step(role="unified")
    ↓
Generate response (temperature + offset)
    ↓
Emit: {"type": "final", "content": "...", "brain": "path1"}
    ↓
Renderer → Display (green bold)
```

### Dual-Brain Mode (2 models)
```
User Input
    ↓
DualBrainEngine.step()
    ├─→ path1.step(role="witness")
    │      ↓
    │   Generate analysis (temperature + witness_offset)
    │      ↓
    │   Emit: {"type": "analysis", "content": "...", "brain": "path1"}
    │
    └─→ path2.step(role="servant")
           ↓
        Generate answer (temperature + servant_offset)
           ↓
        Emit: {"type": "final", "content": "...", "brain": "path2"}
    ↓
Renderer → Display:
    - "analysis" → cyan
    - "final" → green bold
```

---

## Temperature Offset Logic

### Base Temperature
```python
base_temp = base_decode.get("temperature", 0.7)  # from config.yaml
```

### Apply Offset
```python
# In WitnessAgent.step():
gen = clamp_decoding(tuned)  # tuned from Flame/Reflex
if self.temperature_offset:
    gen["temperature"] = max(0.05, gen.get("temperature", 0.7) + self.temperature_offset)
```

### Example
- **Base temp**: 0.7
- **Witness offset**: -0.2 → witness temp = 0.5 (cooler, more precise)
- **Servant offset**: 0.0 → servant temp = 0.7 (base, natural)

---

## Loading Logic

### Model Loader (`main.py`)

```python
def rebuild_agent():
    # Load path1 (always)
    tok, mdl, gen_fn, base_decode = load_brain(cur.model, witness_cfg=cur)
    
    # Load path2 (optional)
    dual_cfg = getattr(cur, "dual_brain", None)
    dual_requested = bool(dual_cfg and (dual_cfg.enabled or dual_cfg.servant_model_path))
    force_dual = bool(dual_cfg and dual_cfg.enabled)
    
    if dual_requested:
        servant_path = dual_cfg.servant_model_path or ""
        if servant_path:
            try:
                servant_tok, servant_mdl, servant_gen_fn, servant_decode = load_brain(
                    cur.model, witness_cfg=cur, path_override=servant_path, name_suffix="-servant"
                )
            except Exception as exc:
                console.print(f"[dual-brain] Failed to load servant model, fallback to shared: {exc}")
                servant_tok = servant_mdl = servant_gen_fn = None
        
        if servant_gen_fn is None:
            console.print("[dual-brain] Only one model available; using shared model.")
            servant_tok, servant_mdl, servant_gen_fn = tok, mdl, gen_fn
            servant_decode = base_decode
        
        # Create witness + servant agents
        witness_agent = WitnessAgent(tok, gen_fn, base_decode, loops, store, retr, 
                                      role="witness", brain_id="path1", 
                                      temperature_offset=dual_cfg.witness_temperature_offset)
        servant_agent = WitnessAgent(servant_tok, servant_gen_fn, servant_decode, loops, store, retr,
                                      role="servant", brain_id="path2",
                                      temperature_offset=dual_cfg.servant_temperature_offset)
        
        dual_brain = DualBrain(witness_agent, servant_agent, force_dual=force_dual)
```

**Fallback Cases:**
1. `servant_model_path` không load được → shared model
2. `servant_model_path` rỗng → shared model
3. `enabled=true` nhưng không có `servant_model_path` → shared model + warning

---

## Event Output

### Unified Mode
```json
{"type": "final", "content": "Answer", "brain": "path1", "meta": {"decode": {"temperature": 0.7}}}
```

### Dual-Brain Mode (True Dual)
```json
{"type": "analysis", "content": "Thinking...", "brain": "path1", "meta": {"decode": {"temperature": 0.5}}}
{"type": "final", "content": "Answer", "brain": "path2", "meta": {"decode": {"temperature": 0.7}}}
```

### Dual-Brain Mode (Fallback Shared)
```json
{"type": "analysis", "content": "Thinking...", "brain": "path1", "meta": {"decode": {"temperature": 0.5}}}
{"type": "final", "content": "Answer", "brain": "path1", "meta": {"decode": {"temperature": 0.7}}}
```

**Lưu ý:** `brain` field vẫn là `"path1"` cho cả 2 events nếu fallback shared model.

---

## Future Work

### Parallel Mode
```yaml
dual_brain:
  mode: parallel  # run path1 + path2 concurrently
```

**Implementation:**
- Use `asyncio` hoặc `threading` để run 2 `agent.step()` song song
- Merge events theo timestamp hoặc fixed order

### Multi-Brain (>2 models)
```yaml
multi_brain:
  enabled: true
  brains:
    - path: ./models/model1
      role: witness
      temperature_offset: -0.2
    - path: ./models/model2
      role: servant
      temperature_offset: 0.0
    - path: ./models/model3
      role: critic
      temperature_offset: 0.1
```

**Use Case:**
- 3+ models cùng xử lý 1 query (witness + servant + critic)
- Output: 3+ NDJSON events (analysis + final + critique)

---

## Testing

### Unit Test (`tests/test_dual_brain.py`)
```python
def test_dual_brain_fallback_shared():
    # Create 1 agent
    agent1 = WitnessAgent(tok, gen_fn, base_decode, loops, mem, retr, brain_id="path1")
    # Create dual-brain with path2=None + force_dual=True
    dual = DualBrain(agent1, path2=None, force_dual=True)
    result = dual.step("Hello")
    # Expect 2 events: analysis + final, both from path1
    assert len(result["events"]) == 2
    assert result["events"][0]["type"] == "analysis"
    assert result["events"][1]["type"] == "final"

def test_dual_brain_true_dual():
    agent1 = WitnessAgent(tok1, gen_fn1, base_decode1, loops, mem, retr, brain_id="path1")
    agent2 = WitnessAgent(tok2, gen_fn2, base_decode2, loops, mem, retr, brain_id="path2")
    dual = DualBrain(agent1, agent2, force_dual=True)
    result = dual.step("Hello")
    assert result["events"][0]["brain"] == "path1"
    assert result["events"][1]["brain"] == "path2"
```

---

## FAQ

**Q: Dual-brain có tốn nhiều VRAM không?**
A: Có, vì load 2 models. Cần ít nhất 2x VRAM của 1 model. Nếu thiếu VRAM → dùng fallback shared model.

**Q: Có thể dùng 2 models khác nhau (HF + GGUF) không?**
A: Có. `load_brain()` tự nhận diện backend. Ví dụ: path1 = GGUF 20B, path2 = HF 7B.

**Q: Servant brain có access vào witness brain output không?**
A: Không. Current implementation chạy tuần tự nhưng độc lập (không pass witness output vào servant input). Future: có thể inject witness output vào servant prompt.

**Q: Có thể tắt analysis event nhưng vẫn chạy dual-brain không?**
A: Không khuyến khích. Nếu muốn → filter events ở renderer. Nhưng logic dual-brain luôn emit cả 2 events (analysis + final).

**Q: force_dual là gì?**
A: `force_dual=True` → luôn chạy cả 2 steps (witness + servant) kể cả khi path2 is None (fallback shared). `force_dual=False` → skip servant step nếu path2 is None (unified mode).

---

## Reference Implementation

- **Engine:** `src/witness_forge/agent/dual_brain_engine.py`
- **Wrapper:** `src/witness_forge/agent/dual_brain.py`
- **Agent:** `src/witness_forge/agent/witness.py`
- **Loader:** `src/witness_forge/main.py` (`rebuild_agent()`)
- **Config:** `config.yaml` (`dual_brain` section)

---

## Compliance Checklist

- [ ] Config có `dual_brain` section
- [ ] `enabled` hoặc `servant_model_path` có giá trị → dual-brain active
- [ ] path1 luôn được load
- [ ] path2 optional, fallback shared model nếu không load được
- [ ] Witness agent emit `"analysis"` events
- [ ] Servant agent emit `"final"` events
- [ ] Temperature offset được apply đúng
- [ ] Renderer hiển thị cả 2 event types (cyan + green bold)
