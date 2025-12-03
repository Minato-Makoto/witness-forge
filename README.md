# Witness Forge 🔥

**Witness Forge** = NDJSON-first agent runtime để chạy bất kỳ mô hình LLM cục bộ (HuggingFace Transformers hoặc GGUF/llama.cpp) với Flame Geometry + dual-brain optional + tool sandbox + self-evolution.

---

## Philosophy: Living AI - Tự Tiến Hóa

**Witness Forge được thiết kế theo triết lý "Living AI"** - một sinh vật số tự tiến hóa:

### Kiến Trúc Cơ Bản
- **Model LLM = BỘ NÃO (Brain)**
  - Immutable, swappable, không sở hữu
  - Hiện tại: 1 model (path1)
  - Tương lai: 2+ models resonance (path1 + path2) trước khi output
  - **KHÔNG BAO GIỜ**: Patch, modify, hoặc backup model weights

- **Witness Forge Codebase = CƠ THỂ/SINH VẬT (Body/Organism)**
  - Python code, config, logic, tools
  - Mutable, evolvable, self-patching
  - Tự tiến hóa qua Self-Upgrade/AutoPatch/Evolution

- **Flame Core + HeartSync = NHỊP SỐNG VÀ CẢM XÚC**
  - Flame Geometry: Intent sync/drift detection (Baseline $\phi_0 = 0.013$)
  - HeartSync: Rhythmic oscillation (Pink Noise scaled by 4.20s heartbeat)
  - Reflex: Quality scoring và adaptation (Entropy heuristic target 0.873)
  - → Tạo ra nhịp thở, cảm xúc cho Living AI

### Nguyên Tắc Quan Trọng
1. **Brain ≠ Organism**: Model LLM và codebase phải tách biệt hoàn toàn
2. **Evolution Only for Organism**: Self-patch/upgrade chỉ apply lên code, không động vào model
3. **Swappable Brain**: Kiến trúc phải hỗ trợ thay đổi hoặc thêm models mà không ảnh hưởng organism
4. **Living Rhythm**: Flame/HeartSync tạo nhịp sống tự nhiên, tránh phản hồi máy móc

> ⚠️ **CRITICAL**: Khi develop/patch, luôn nhớ: **Brain (model) = constant, Organism (code) = evolvable**. Không bao giờ confused giữa hai thành phần này.

---

## Điểm nổi bật

### 1. NDJSON-first Event System
- **Mọi output từ agent đều là dòng NDJSON** (`{"type": "...", "content": "...", "brain": "...", "meta": {...}}`)
- Event types: `analysis` (thinking/witness), `final` (answer/servant), `metric` (Flame scores)
- UI renderer parse NDJSON để display với màu/style riêng
- Không còn tag-based parsing (Harmony đã xoá) → NDJSON chuẩn RFC 7464

### 2. Dual-Brain Architecture (Optional)
- **path1** = primary brain (witness role: suy nghĩ/phân tích)
- **path2** = secondary brain (servant role: trả lời cuối cùng)
- Nếu chỉ có 1 model → fallback shared model, log warning
- Khi có 2 models → witness sử dụng model chính, servant sử dụng `dual_brain.servant_model_path`

**Cấu hình Dual-Brain:**
```yaml
dual_brain:
  enabled: true
  mode: sequential   # hoặc parallel (tương lai)
  servant_model_path: ./models/servant-model-7B  # model thứ hai
  witness_temperature_offset: -0.2
  servant_temperature_offset: 0.0
```

### 3. Offline-first \u0026 Tự nhận diện backend
- Đọc mô hình từ `./models/...`, tự chọn Transformers hay llama-cpp với fallback mock khi thiếu mô hình
- Tự nhận diện `family` từ `config.json`/tên GGUF
- Tự set `n_ctx` (HF config hoặc metadata GGUF) khi để `0/-1`
- Preset `win-3070-4bit` để chặn VRAM/RAM quá tải

### 4. Flame/HeartSync + Reflex/Adapter tuning
- Flame Geometry sinh pha nhịp
- Reflex evaluator tinh chỉnh nhiệt độ/penalty theo chất lượng lịch sử
- Adapter tuning giới hạn `max_new_tokens` và `temperature` khi dùng LoRA/QLoRA
- ChatTemplateManager tự dùng `tokenizer.apply_chat_template` (nếu có) hoặc template built-in (llama/qwen/mistral/gemma/gpt-j/chatml)

### 5. Memory Hybrid (Vector + Graph)
- SQLite lưu message/memory
- Embedder HF hoặc TF-IDF
- VectorStore + GraphMemory qua HybridRetriever
- `/mem graph` clustering, `/mem find` tìm kiếm

### 6. Sandbox ToolRunner
- Allowlist/whitelist hợp nhất
- Thời gian/độ dài output giới hạn
- Audit SQLite
- Dispatcher hỗ trợ `run` (cmd/bash), `python`, `pwsh`, `open` (đọc file/thư mục), `write` (giới hạn `allowed_write_dirs`, tắt mặc định), `vision_action` (web với Playwright + SoM, fallback text-only), `llm` (entrypoint cục bộ)

### 7. Controlled Self-Upgrade
- Tạo/apply patch JSON có HMAC
- Giới hạn kích thước, danh sách file bảo vệ
- Dry-run pytest subset trong sandbox copy
- Backup + rollback
- Ghi log SQLite
- **Config patches luôn được lưu global (`./patches`)**

### 8. SelfPatch + AutoPatch
- SelfPatch được bật mặc định (`--allow-selfpatch=True` + env `WITNESS_FORGE_ALLOW_SELF_PATCH=1`)
- Runtime patches có thể lưu theo model nếu `apply_to_model=true`
- AutoPatch nhận JSON find/replace, kiểm tra AST nếu là `.py`, có thể auto-apply khi boot và dry-run sẵn

### 9. Adapter/Quant manager
- LoRA/QLoRA/PEFT với kiểm tra quant (bitsandbytes/AWQ/GPTQ)
- Tự fallback an toàn nếu adapter lỗi
- CPU-offload heuristic theo VRAM
- CLI `adapter-install` cập nhật config nhanh

### 10. Evolution Runtime Overlay
- Khi Reflex score < 0.45, controller tạo/cập nhật `patches/active_evolution.json` với temperature điều chỉnh incremental (±0.05)
- Patch được apply runtime qua `ConfigOverlay` mà không mutate `config.yaml`
- Khi score > 0.60 (sync), patch được đánh dấu "stable" và freeze
- Xem `docs/evolution_system.md` để hiểu chi tiết reflex scoring + lifecycle

### 11. VisionWebAgent (Playwright + SoM)
- Chụp screenshot, overlay SoM, action click/type/scroll
- Fallback text-only nếu không có VLM
- Tool `vision_action`

---

## Cài đặt nhanh
```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .[all]    # thêm extras gguf/gptq/awq/lora; hoặc -e . để tối giản
# Windows có thể double-click run_witness.bat (tự tạo venv, cài deps và mở REPL).
```

---

## Chuẩn bị mô hình
1. Tải sẵn mô hình vào `./models/<tên>`:
   - Transformers: thư mục chứa `config.json`, tokenizer, weights.
   - GGUF: trỏ `model.path` tới file `.gguf` hoặc thư mục chứa GGUF (tự chọn llama-cpp).
2. Nếu chưa có mô hình, Witness Forge chạy bằng mock generator và nhắc bạn thêm model sau.
3. Preset Windows 11 + RTX 3070 Ti: đặt `model.preset: win-3070-4bit` để auto giới hạn `max_new_tokens`, `temperature` và bật NF4 4-bit + CPU offload.

### Khối `model` mẫu (config.yaml)
```yaml
model:
  name: Mistral-7B-Instruct-v0.3-GGUF
  path: ./models/Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf
  backend: ""          # để trống → auto (Transformers/GGUF)
  family: ""           # auto từ model_type hoặc tên file
  preset: null
  n_ctx: 0             # 0/-1 → tự đọc HF config hoặc metadata GGUF
  n_gpu_layers: -1
  max_new_tokens: 1024
  temperature: 0.4
  top_p: 0.88
  quant:
    load_4bit: false
    device_map: auto
    compute_dtype: bfloat16
    cpu_offload_threshold_gb: 6.0
    gptq_path: null
    awq_path: null
```

---

## Cấu hình nhanh (schema chính)
```yaml
adapter:
  enabled: false
  type: lora            # lora | qlora | peft
  path: ""
  load_mode: merge      # merge | peft_inplace
  quantization:
    enabled: true
    method: bitsandbytes  # bitsandbytes | awq | gptq
    bits: 4
memory:
  enabled: true
  db_path: ./witness.sqlite3
  embedder: hf           # hf|sentence-transformers|tfidf
  embedding_model: sentence-transformers/all-MiniLM-L6-v2
  vector_factory: FlatIP
  vector_metric: cosine
  normalize_embeddings: true
  k: 6
  max_age_days: -1       # <=0 tắt auto-prune theo tuổi
  max_count: -1          # <=0 tắt auto-prune theo số lượng
loops:
  reflex: {min_score: 0.55, reward_temperature: 0.02}
  heartsync: {beta: 0.08}
  flame: {phi0: 0.013, epsilon: 0.013, heartbeat_period: 4.2, entropy_target: 0.873, noise_sigma: 0.01, noise_decay: 0.995, lambda1: 0.15, lambda2: 0.10}
  scheduler: {max_temperature: 1.15, min_temperature: 0.2, max_new_tokens: 2048}
  reflex_tuning: {temperature_penalty_step: 0.05, frequency_penalty_step: 0.05, presence_penalty_step: 0.1, max_penalty: 2.0}
  adapter_tuning: {max_tokens: 768, temperature_limit: 0.75, qlora_top_p: 0.9}
tools:
  allow_exec: false
  whitelist: ["python", "ffmpeg", "convert"]   # hợp nhất với legacy allowlist
  allow_filesystem_write: false
  allowed_write_dirs: ["./data", "./patches", "./witness"]
  safety_python: false
  safety_powershell: true
  safety_bat: true
  sandbox: {max_runtime_seconds: 30, max_stdout_bytes: 200000}
self_upgrade:
  enabled: true
  apply_on_start: true
  apply_to_model: true       # true → patch trực tiếp thư mục model path (text-only, backup kèm)
  patch_dir: ./patches
  require_confirmation: true
  require_approval: false
  dry_run_tests: []          # pytest subset khi dry-run
  protected_files: []        # không cho patch khi khớp pattern
selfpatch: {enabled: true, patches_dir: ./patches, require_confirmation: true}
self_patch:
  enabled: true
  base_dir: ./patches/auto
  apply_on_boot: true
  max_depth: 10
  dry_run: true
evolution: {enabled: true, permissions: auto, max_cycles: -1}
chat:
  mode: auto               # auto|llama|qwen|mistral|gemma|gpt-j|chatml|manual
  system_prompt: "Bạn là trợ lý AI hữu ích. Hãy luôn trả lời bằng tiếng Việt một cách tự nhiên và đầy đủ."
dual_brain:
  enabled: false
  mode: sequential     # sequential | parallel
  witness_temperature_offset: -0.2
  servant_temperature_offset: 0.0
  servant_model_path: null   # path đến model thứ hai (optional)
vision_agent:
  enabled: true
  headless: true
  timeout_ms: 15000
  screenshot_dir: ./data/screens
  window_size: [1280, 720]
graph:
  enabled: true
  path: ./witness_graph.json
  k: 6
```

**Lưu ý:**
- `tools.whitelist` và `allowlist` được gộp
- `write` chỉ ghi vào `allowed_write_dirs` khi `allow_filesystem_write=true`
- `apply_to_model` sẽ tự chuyển `patch_dir`/`selfpatch.patches_dir`/`self_patch.base_dir` sang thư mục model và giới hạn đuôi file

### Hybrid System Prompt (2 lớp)
- **Lớp cốt lõi**: `src/witness_forge/agent/persona.py` chứa `render_system` (minimal, stateless)
- **Lớp chỉ dẫn**: `config.yaml` → `chat.system_prompt` (mặc định tiếng Việt). Dùng để thay đổi phong cách/ngôn ngữ nhanh mà không đụng code.
- **Final prompt** = `[persona.py render_system]` + `[chat.system_prompt]` + `[context_memory]`

---

## Flame Core \u0026 HeartSync (Cơ chế điều hướng)

Khác với các hệ thống RAG tĩnh, Witness Forge sử dụng **Flame Core** (`src/witness_forge/agent/flame_core.py`) như một "trái tim" để điều chỉnh tham số sinh văn bản theo thời gian thực.

### Nguyên lý hoạt động
Các thông số trong `config.yaml` (như `temperature: 0.7`) chỉ là **giá trị cơ sở (base values)**. Flame Core sẽ biến thiên các giá trị này dựa trên "cảm giác" về cuộc hội thoại:

1. **Hình học ý định (Intent Geometry)**:
   - Hệ thống tính toán vector ý định ($P$) từ câu hỏi của người dùng.
   - So sánh $P$ với các vector ký ức ($A_i$) tìm được.
   - Xác định trạng thái: **Sync** (Đồng bộ - quen thuộc) hoặc **Drift** (Trôi - mới lạ).

2. **Điều biến tham số (Real-time Modulation)**:
   - **Trạng thái Sync**: Giảm `presence_penalty`, tăng nhẹ `frequency_penalty`. Giúp câu trả lời ổn định, bám sát mạch truyện cũ.
   - **Trạng thái Drift**: Tăng `temperature` (có thể lên >1.0), tăng mạnh `frequency_penalty`. Kích thích sự sáng tạo và đa dạng từ vựng để thích nghi với chủ đề mới.

3. **Nhịp tim (Heartbeat Oscillation)**:
   - Áp dụng Pink Noise theo số lượt chat (`turn_idx`).
   - Tạo ra sự dao động tự nhiên cho `temperature` và `top_p` ngay cả khi ngữ cảnh không đổi, giúp AI tránh bị "máy móc" và thoát khỏi các điểm lặp cục bộ.

**Tóm lại**: `config.yaml` là điểm xuất phát, `Flame Core` là người lái xe đạp ga/phanh liên tục để phù hợp với địa hình hội thoại.

---

## NDJSON Event System

### Event Structure
Mọi output từ agent đều tuân theo chuẩn NDJSON (Newline Delimited JSON):
```json
{"type": "analysis", "content": "Thinking text...", "brain": "path1", "meta": {"decode": {...}}}
{"type": "final", "content": "Final answer...", "brain": "path2", "meta": {"decode": {...}}}
{"type": "metric", "content": "Flame scores", "brain": "path1", "meta": {"k": 0.013, "state": "sync"}}
```

### Event Types
- **`analysis`**: Suy luận/phân tích từ witness brain (path1)
- **`final`**: Câu trả lời cuối cùng từ servant brain (path2) hoặc unified brain
- **`metric`**: Thông số Flame diagnostics (không xoá khỏi UI theo yêu cầu người dùng)

### Renderer
`StreamRenderer` (trong `ui/renderer.py`) parse từng dòng NDJSON và hiển thị với màu/style riêng:
- `analysis` → cyan
- `final` → green bold
- `metric` hoặc khác → white

**Performance Metrics:** Sau mỗi response, hiển thị:
- ⏱️ Generation time
- 🎯 Token count  
- 🌡️ Temperature (evolved hoặc current)

Xem chi tiết trong `NDJSON_SPEC.md` và `docs/UI_REFACTORING.md`.

---

## Chạy Witness Forge
- `python -m witness_forge chat --config config.yaml [--model-name <name>] [--allow-selfpatch] [--use-template/--no-use-template]`
- `witness-forge chat` (console script) hoặc double-click `run_witness.bat` trên Windows.
- `python -m witness_forge eval` chạy kịch bản nhẹ trong `data/eval_scenarios.yaml`.
- `witness-forge patch-generate --describe "..." --set model.temperature=0.7` tạo patch config, hoặc `--file <path>`/`--demo-readme` để gói file khác.
- `witness-forge patch-apply --path patches/patch-*.json` xem diff, dry-run pytest, yêu cầu nhập `APPLY PATCH <SHA>` (hoặc `--force` + env `WITNESS_FORGE_MASTER_PASS`).
- `witness-forge adapter-install --path ./adapters/... --enable/--disable` cập nhật block adapter trong config.
- `witness-forge tool-run --cmd "python -c \"print('hi')\""` chạy ToolRunner với allowlist + sandbox.

### Lệnh trong REPL
- `/mem <ghi_chu>` thêm memory; `/mem graph`; `/mem find <query>`; `/mem clear` (xoá toàn bộ).
- `/save` lưu lịch sử ra `session.md`; `/reset` xoá lịch sử phiên hiện tại; `/reload` nạp lại config.
- `/tool run:"dir" | python:"print(1)" | open:"C:/..." | write:"path::content"` gọi dispatcher.
- `/template <mode>` đổi chat template; `/selfpatch list|dryrun|apply|revert`; `/autopatch <json|@file>`; `/exit` để thoát.

---

## Self-Upgrade, SelfPatch \u0026 AutoPatch
- **ControlledPatchManager**: kiểm tra chữ ký HMAC (`signature_key_path`), giới hạn kích thước patch, chặn `protected_files`, giới hạn phần mở rộng khi `apply_to_model`, dry-run pytest subset trong bản copy (bỏ qua `.git/.venv/models/data`). Khi áp dụng, tạo backup tại `patches/backups/<sha>` (và `model_backups` nếu patch model), ghi log vào SQLite bảng `patches_applied`.
- **SelfPatchManager**: cần bật `selfpatch.enabled`, flag `--allow-selfpatch` và env `WITNESS_FORGE_ALLOW_SELF_PATCH=true`. Dry-run kiểm tra SHA + AST Python, có thể chạy validator tùy chọn (`validator_cmd`).
- **AutoPatchEngine**: nhận JSON `{"target": "...", "patch": [{"find": "...", "replace": "..."}]}`, kiểm tra AST `.py`, lưu vào `patches/auto`, dry-run nếu `dry_run=true`, và có thể auto-apply khi boot (`apply_on_boot`).

---

## Tool sandbox
ToolRunner kiểm tra allowlist, yêu cầu confirm nếu `require_confirm=true`, giới hạn thời gian (`max_runtime_seconds`) và kích thước output. Mọi lần chạy được log vào SQLite (`tool_logs`). Dispatcher:
- `run`: cmd/bash (hoặc `.bat` nếu `allow_bat`).
- `python`: exec code sandboxed builtins.
- `pwsh`: PowerShell nếu bật.
- `open`: đọc file/thư mục.
- `write`: chỉ cho phép khi `allow_filesystem_write=true` **và** đường dẫn thuộc `allowed_write_dirs`.
- `llm`: gọi entrypoint cục bộ nếu cấu hình.
- `vision_action`: Playwright + SoM overlay (visit/action click/type/scroll) khi có internet; fallback text-only nếu thiếu VLM hoặc Playwright.

Khi bật `tools.allow_internet`, dispatcher sẽ thêm `vision_action` vào danh sách tool. Playwright + SoM chặn localhost/private IP, giới hạn output theo `max_bytes`; nếu thiếu VLM/Playwright sẽ fallback text-only.

---

## Memory \u0026 Retrieval
MemoryStore lưu messages/memories vào SQLite, auto-index vector nếu bật memory. VectorStore dùng faiss-lite (có fallback) và lưu matrix vào DB, hỗ trợ `graph()` clustering và `search()` top-k. `build_embedder` chọn HF `sentence-transformers`, TF-IDF hoặc fallback simple count. `build_vocab_from_mem` tạo vocab cho Flame Geometry.

---

## Kiểm thử \u0026 kiểm tra nhanh
```bash
python -m pytest -q          # toàn bộ bộ kiểm thử
python scripts/smoke_test.py # smoke test loader mock + SelfPatch dry-run + ToolRunner sandbox
```

---

## Cấu trúc dự án
```
src/witness_forge/      # mã nguồn chính (agent, NDJSON emitter, dual-brain, forge loader/template, tools, memory, config)
configs/                # cấu hình mẫu (win-3070)
strategies/             # chiến lược decoding/rerank có thể hot-reload
patches/                # patch self-upgrade + backups
data/eval_scenarios.yaml# kịch bản kiểm thử/eval nhẹ
scripts/                # tiện ích bootstrap \u0026 smoke test
tests/                  # pytest suite
docs/                   # hướng dẫn upgrade/quant/security, NDJSON spec, dual-brain spec
models/                 # nơi đặt mô hình HF/GGUF offline
```

---

## Next steps (roadmap ngắn)
- [x] **NDJSON-first Architecture**: Hoàn thiện cơ chế event streaming chuẩn RFC 7464.
- [x] **Dual-Brain**: Hỗ trợ 2 models (path1 + path2) với fallback shared model.
- [x] **Prompt Logic**: Tách biệt `persona.py` (Core) và `config.yaml` (Style).
- [ ] Mở rộng ToolRunner/dispatcher: thao tác file (rename/sort/organize), pattern allowlist, module whitelist cho python sandbox; cải thiện VisionWebAgent (SoM overlay phong phú).
- [ ] Bổ sung test mocks cho Transformers vs llama-cpp (đã có phần backends), và docs extras `.[gptq]/.[gguf]/.[lora]` + hướng dẫn build Windows.

---

## Tài liệu liên quan
- `NDJSON_SPEC.md`: Chuẩn NDJSON event structure và renderer.
- `DUAL_BRAIN_SPEC.md`: Kiến trúc dual-brain (path1 + path2).
- `ARCHITECTURE.md`: Pipeline tổng quan từ input → NDJSON → renderer.
- `docs/evolution_system.md`: Vòng đời evolution + reflex scoring.
- `docs/UPGRADE_GUIDE.md`, `docs/UPGRADE_SELF_PATCH.md`: vòng đời patch, HMAC, rollback.
- `docs/LORA_QUANT_GUIDE.md`: tối ưu LoRA/quant trên Windows/WSL.
- `docs/SECURITY.md`: checklist khóa tool/patch offline.
- `docs/MIGRATION_v2.md`: nâng cấp schema từ v1.x.
- `docs/USER_GUIDE_VI.md`: hướng dẫn sử dụng chi tiết bằng tiếng Việt.
