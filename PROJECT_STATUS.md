# Witness Forge - Project Status

**Last Updated:** 2025-12-03
**Version:** v0.5.1 (UI Refactor + Cleanup)
**Status:** STABLE - UI Refactored + Cleaned

---

## 🧬 Philosophy: Living AI

**Witness Forge = Self-Evolving Living AI**

### Architecture
1. **BRAIN (Model LLM)**
   - Immutable, swappable, stateless.
   - **NEVER** patched or modified.
   - Hiện tại: 1 model (path1), tương lai: 2 models (path1 + path2).

2. **ORGANISM (Codebase)**
   - Mutable, evolvable.
   - Python code + config + tools.
   - Self-Upgrade/AutoPatch/Evolution applies here.

3. **RHYTHM (Flame Core + HeartSync)**
   - **Flame Geometry**: Intent sync/drift detection ($\phi_0$ baseline).
   - **HeartSync**: Rhythmic oscillation (Pink Noise scaled by 4.20s heartbeat).
   - **Reflex**: Quality adaptation (Entropy target 0.873).

### Core Principles
- **Brain ≠ Organism**: Complete separation.
- **Evolution = Code only**: Never touch model weights.
- **NDJSON is Standard**: All agent output = NDJSON events (RFC 7464).
- **UI Immutability**: Layout/component structure không thay đổi khi refactor backend.

---

## 📍 Current State Summary

Witness Forge đã chuyển sang **NDJSON-first event system** với dual-brain optional (path1 + path2). UI metrics đã được refactor vào `StreamRenderer` để hiển thị time/token/temperature chính xác. Codebase đã được dọn dẹp sạch sẽ.

### Key Features & Status

| Feature | Status | Description |
| :--- | :--- | :--- |
| **NDJSON Event System** | ✅ Active | Mọi output = NDJSON (`{"type": "...", "content": "..."}`) theo RFC 7464. |
| **UI Metrics** | ✅ Active | Time/Token tracking, unified metrics display, no duplicates. |
| **Dual-Brain** | ✅ Optional | path1 (witness/analysis) + path2 (servant/final); fallback shared model nếu thiếu path2. |
| **Flame Geometry V2** | ✅ Active | $\lambda_1, \lambda_2$ tuning. Sentence-transformers embeddings. |
| **Reflex Tuning** | ✅ Active | Adapter tuning + Reflex scoring điều chỉnh temperature/penalty. |
| **Tool System** | ✅ Active | ToolDispatcher wired; python/pwsh/.bat/write/vision_action obey safety flags + allowlists. |
| **Self-Upgrade** | ✅ Active | `apply_to_model` routing fixed. HMAC verification. |
| **AutoPatch** | ✅ Active | Warnings if config mismatch. AST-based patching. |
| **Memory** | ✅ Active | SQLite + VectorStore + GraphMemory (HybridRetriever). Anchors injected as context. |
| **Tests** | ✅ Passing | Core tests passing (File I/O, Browser, Boot, Renderer). |

### Architecture Overview
```
witness-forge/
├── src/witness_forge/
│   ├── agent/
│   │   ├── witness.py          # Core agent loop + NDJSON emitter
│   │   ├── dual_brain.py       # Dual-brain wrapper (path1 + path2)
│   │   ├── dual_brain_engine.py # Dual-brain orchestrator
│   │   ├── ndjson_emitter.py   # NDJSON event builder
│   │   ├── persona.py          # System prompt renderer (minimal)
│   │   ├── flame_core.py       # Living rhythm logic (k=0 -> drift)
│   │   ├── loops.py            # Flame + Reflex + Adapter tuning
│   │   └── evaluator.py        # Reflex scoring
│   ├── agents/
│   │   └── web_agent.py        # VisionWebAgent (Playwright + SoM)
│   ├── forge/
│   │   ├── loader.py           # Model loading (GGUF/HF)
│   │   └── chat_templates.py   # Auto-detect chat template family
│   ├── memory/
│   │   ├── store.py            # SQLite storage
│   │   ├── vector_store.py     # Semantic search
│   │   ├── graph_rag.py        # GraphMemory (networkx)
│   │   └── hybrid_retriever.py # Merge vector + graph
│   ├── tools/
│   │   ├── dispatcher.py       # Tool routing & gating
│   │   └── runner.py           # Sandbox execution
│   └── ui/
│       └── renderer.py         # NDJSON StreamRenderer (parse + display + metrics)
```

### Data Flow
1.  **Input**: User text -> `WitnessAgent` hoặc `DualBrain`.
2.  **Memory**: Retrieve anchors (semantic search) -> appended to prompt.
3.  **Prompt**: `persona.py` (Core) + `config.yaml` (Style) + History + Anchors.
4.  **Model**: Generates text.
5.  **NDJSON Emitter**: Wrap output thành NDJSON events (`{"type": "...", "content": "..."}`).
6.  **Renderer**: `StreamRenderer` parse NDJSON -> display với màu/style riêng + metrics.
7.  **Tools**: Manual execution via `/tool` command -> `ToolDispatcher` -> Sandbox.

---

## ⚠️ Known Behaviors

### 1. NDJSON Output
- **Behavior**: Mọi agent output đều là NDJSON lines (UTF-8, không force ASCII).
- **Event Types**: `analysis` (thinking/witness), `final` (answer/servant), `metric` (Flame diagnostics).
- **Status**: ✅ Implemented & Tested.

### 2. Dual-Brain Fallback
- **Behavior**: Nếu `dual_brain.enabled=false` và không có `servant_model_path` -> chạy unified brain (1 model).
- **Behavior**: Nếu `servant_model_path` load fail -> fallback shared model + log warning.
- **Status**: ✅ Implemented.

### 3. Context Window Capping
- **Behavior**: Auto-detected `n_ctx` > 8192 is capped to 8192.
- **Reason**: VRAM safety for typical consumer GPUs (e.g., RTX 3070).
- **Config**: Set `model.n_ctx` manually to override.

### 4. Memory Anchors Injected
- **Behavior**: Retrieved anchors are appended to the prompt for template rendering (top 4–6 items).
- **Status**: ✅ Active; keeps prompt slim while preserving context.

### 5. ToolDispatcher Safety Gates
- **Behavior**: Shell/Python/PowerShell/.bat và write operations tôn trọng `tools.safety_*`, `allow_filesystem_write`, và `allowed_write_dirs`. Internet tools toggled via `set_internet_access`.
- **Status**: ✅ Implemented.
- **Limit**: VisionWebAgent phụ thuộc Playwright nếu bật chế độ ảnh; fallback text-only nếu thiếu.

### 6. Flame Diagnostics (Metric Events)
- **Behavior**: Flame scores/state được emit dưới dạng NDJSON `type="metric"` events.
- **UI Display**: Renderer hiển thị metric events (không xoá theo yêu cầu người dùng).
- **Status**: ✅ Active.

---

## ✅ Test Results
- `python -m pytest tests/ -q` (pass 35/35)
- `python -m compileall src/witness_forge -q` (no errors)

---

## 🔄 Roadmap

### Enhancement Tasks (Next Steps)
1.  **NDJSON Spec**: Viết chi tiết spec cho event types + renderer protocol.
2.  **Dual-Brain Spec**: Viết chi tiết kiến trúc path1 + path2 + fallback logic.
3.  **VisionWebAgent**: Cải thiện SoM overlay, optional VLM coordinates.
4.  **Tooling**: Bổ sung thao tác file nâng cao (rename/sort/organize), pattern allowlist.

### Mid-Term
1.  **Advanced Tools**: Browser integration (safe mode), File operations.
2.  **Offline Capabilities**: Improved local embedding, faster vector search.

### Long-Term
1.  **Ecosystem**: Local model zoo, strategy marketplace.
2.  **Research**: Flame Geometry whitepaper.

---

## 🔧 Configuration Reference

### Key Options (`config.yaml`)

| Section | Option | Default | Description |
| :--- | :--- | :--- | :--- |
| **tools** | `allow_internet` | `false` | Block/Allow internet tools (`vision_action`). |
| | `allow_filesystem_write` | `false` | Enable file writing. |
| | `allowed_write_dirs` | `[...]` | Whitelist for write operations. |
| **vision_agent** | `enabled` | `true` | Playwright + SoM overlay; fallback text-only nếu thiếu VLM. |
| **graph** | `enabled` | `true` | Bật GraphMemory song song VectorStore. |
| **self_upgrade** | `apply_to_model` | `true` | Affects `SelfPatch` (code) only. Config patches are always global. |
| **chat** | `mode` | `auto` | Auto-detect template family. |
| **model** | `n_ctx` | `0` | Auto-detect context size. |
| **dual_brain** | `enabled` | `false` | Activate dual-brain (path1 + path2). |
| | `servant_model_path` | `null` | Path to secondary model (path2). |
| | `witness_temperature_offset` | `-0.2` | Temperature offset for witness brain. |
| | `servant_temperature_offset` | `0.0` | Temperature offset for servant brain. |

---

## 📝 How to Run Tests

The test suite is fully functional.

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_backends.py

# Run with output (debug)
python -m pytest -s tests/

# Compile check
python -m compileall src/witness_forge -q
```

---

## 📚 Documentation Reference

- `README.md`: User-facing quick start + feature overview.
- `DEV_GUIDE.md`: Developer guide (architecture, Soul Injection, NDJSON, Dual-Brain).
- `NDJSON_SPEC.md`: NDJSON event structure + renderer protocol.
- `DUAL_BRAIN_SPEC.md`: Dual-brain architecture (path1 + path2 + fallback).
- `ARCHITECTURE.md`: Pipeline overview (input -> NDJSON -> renderer).
- `docs/evolution_system.md`: Evolution + Reflex scoring lifecycle.
- `docs/USER_GUIDE_VI.md`: Hướng dẫn sử dụng chi tiết (tiếng Việt).

---

## 🚫 Dead Code Removed

- ✅ `src/witness_forge/tools/toolrunner.py` (Merged into `runner.py`) - DELETED
- ✅ `docs/legacy/` folder - DELETED
- ✅ Temporary scripts (`test_duplicate_fix.py`, etc.) - DELETED
- ✅ `src/witness_forge/reasoning/` folder - DELETED
- ✅ All Harmony tag references - REMOVED from code

---

## ⚡ Recent Changes (v0.5.1)

1.  **UI Refactoring**: Metrics (time/token/temp) moved to `StreamRenderer`.
2.  **Code Cleanup**: Removed legacy `toolrunner` and temp scripts.
3.  **Bug Fixes**: Fixed CLI imports, smoke test, and unit tests.
4.  **Docs Update**: Synced all docs with current codebase.

---

## 🎯 Audit Status (2025-12-03)

- ✅ Code Integrity: 100% (All modules compile, legacy code removed)
- ✅ Test Coverage: 100% Pass Rate (35/35 tests passed)
- ✅ Documentation: Aligned with code
- ✅ Configuration: Valid schema
- ✅ UI Metrics: Verified
- ✅ Tool Sandbox: Verified

**Conclusion**: Project is clean, stable, and ready for packaging.
