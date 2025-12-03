# Witness Forge - Comprehensive Project Audit Plan

**Date:** 2025-12-03
**Purpose:** Kiểm tra toàn bộ dự án trước khi update documentation

---

## 🎯 Audit Objectives

1. **Code Integrity**: Verify tất cả modules hoạt động đúng
2. **Feature Completeness**: Confirm tất cả features đã implement
3. **Test Coverage**: Check test suite status
4. **Documentation Alignment**: So sánh code vs docs
5. **Config Validation**: Verify config schema
6. **Architecture Compliance**: Check tuân thủ design principles

---

## 📋 Audit Checklist

### Phase 1: Code Structure & Integrity

#### 1.1. Core Components
- [ ] **agent/witness.py**
  - [ ] `step()` method implementation
  - [ ] NDJSON event emission
  - [ ] Role handling (witness/servant/unified)
  - [ ] Memory integration
  - [ ] Tool integration
  
- [ ] **agent/dual_brain.py**
  - [ ] DualBrain orchestration
  - [ ] Path1/Path2 coordination
  - [ ] Fallback shared model logic
  - [ ] Event merging
  
- [ ] **agent/flame_core.py**
  - [ ] Geometry calculation
  - [ ] Sync/Drift detection
  - [ ] HeartSync (Pink Noise)
  - [ ] Modulation logic
  
- [ ] **agent/loops.py**
  - [ ] Flame integration
  - [ ] Reflex evaluation
  - [ ] Adapter tuning
  - [ ] Loop state assembly
  
- [ ] **agent/evolution.py**
  - [ ] Reflex score monitoring
  - [ ] Patch generation
  - [ ] Freeze/unfreeze logic
  - [ ] Evolution output format

#### 1.2. UI & Rendering
- [ ] **ui/renderer.py**
  - [x] `start_generation()` method
  - [x] `create_stream_callback()` method
  - [x] `print_metrics()` method
  - [x] Time tracking
  - [x] Token counting
  - [x] Duplicate temperature fix
  - [ ] NDJSON parsing
  - [ ] Style mapping

#### 1.3. Model Loading
- [ ] **forge/loader.py**
  - [ ] HuggingFace backend
  - [ ] llama-cpp backend
  - [ ] Auto-detection logic
  - [ ] Quant support (4bit/8bit/GPTQ/AWQ)
  - [ ] CPU offload heuristic
  - [ ] Mock fallback

#### 1.4. Memory System
- [ ] **memory/store.py** - SQLite storage
- [ ] **memory/vector_store.py** - Faiss-lite
- [ ] **memory/graph_rag.py** - NetworkX graph
- [ ] **memory/hybrid_retriever.py** - Merge logic
- [ ] **memory/embedding.py** - Embedder builder

#### 1.5. Tools System
- [ ] **tools/dispatcher.py** - Tool routing
- [ ] **tools/runner.py** - Sandbox execution
- [ ] **agents/web_agent.py** - Playwright + SoM
- [ ] Safety flags validation
- [ ] Allowlist enforcement

#### 1.6. Self-Evolution
- [ ] **agent/self_upgrade.py** - Config patches
- [ ] **agent/selfpatch.py** - Code patches
- [ ] **agent/self_patch.py** - AutoPatch
- [ ] **config_overlay.py** - Runtime overlay
- [ ] HMAC verification
- [ ] Backup/rollback

---

### Phase 2: Feature Verification

#### 2.1. NDJSON System ✅
- [x] Event structure compliant (RFC 7464)
- [x] Event types: analysis, final, metric
- [x] Proper JSON encoding (UTF-8, no ASCII force)
- [ ] Renderer parses correctly
- [ ] No tag-based parsing remnants

#### 2.2. Dual-Brain ⚠️
- [ ] Activation logic (enabled OR servant_model_path)
- [ ] Temperature offsets applied
- [ ] Shared model fallback works
- [ ] Sequential mode works
- [ ] Event ordering (analysis → final)

#### 2.3. Flame System ⚠️
- [ ] Geometry calculation correct
- [ ] Heartbeat oscillation active
- [ ] Entropy target (0.873) applied
- [ ] Phi0 baseline (0.013) used
- [ ] Metrics emit to UI

#### 2.4. Memory & Retrieval ⚠️
- [ ] SQLite tables created
- [ ] Vector indexing works
- [ ] Graph memory persists
- [ ] Hybrid retrieval merges correctly
- [ ] `/mem` commands work

#### 2.5. Tools ⚠️
- [ ] Allowlist enforcement
- [ ] Timeout works
- [ ] Output limits work
- [ ] Audit logging works
- [ ] File write restrictions work
- [ ] Vision agent works (when enabled)

#### 2.6. Evolution ⚠️
- [ ] Reflex scoring works
- [ ] Temperature tuning triggers
- [ ] Patch creation works
- [ ] Patch freeze works
- [ ] Overlay applies runtime

#### 2.7. UI Metrics ✅
- [x] Time tracking works
- [x] Token counting works
- [x] Temperature display works
- [x] No duplicates
- [x] Metrics always visible

---

### Phase 3: Testing

#### 3.1. Unit Tests
- [ ] **test_ndjson_emitter.py** - Pass?
- [ ] **test_dual_brain.py** - Pass?
- [ ] **test_flame_core.py** - Pass?
- [ ] **test_evaluator.py** - Pass?
- [ ] **test_memory.py** - Pass?
- [ ] **test_tool_dispatcher.py** - Pass?
- [ ] **test_backends.py** - Pass?

#### 3.2. Integration Tests
- [ ] **test_boot.py** - Full pipeline boot
- [ ] **test_renderer.py** - NDJSON parsing

#### 3.3. Smoke Test
- [ ] **scripts/smoke_test.py** - Pass?

#### 3.4. Real-World Test
- [ ] Chat interaction works
- [ ] Dual-brain works (if enabled)
- [ ] Evolution occurs
- [ ] Memory persists
- [ ] Tools execute

---

### Phase 4: Configuration

#### 4.1. Schema Validation
- [ ] **config.yaml** structure valid
- [ ] All sections present
- [ ] Defaults reasonable
- [ ] Preset support works

#### 4.2. Config Sections
- [ ] `model` - Complete
- [ ] `adapter` - Complete
- [ ] `memory` - Complete
- [ ] `loops` - Complete (Flame/Reflex/Scheduler)
- [ ] `tools` - Complete
- [ ] `self_upgrade` - Complete
- [ ] `selfpatch` - Complete
- [ ] `self_patch` - Complete
- [ ] `evolution` - Complete
- [ ] `chat` - Complete
- [ ] `dual_brain` - Complete
- [ ] `vision_agent` - Complete
- [ ] `graph` - Complete

---

### Phase 5: Architecture Compliance

#### 5.1. NDJSON-First ✅
- [x] All agent output is NDJSON
- [x] No hardcoded text format
- [x] UTF-8 encoding
- [x] Valid JSON per line

#### 5.2. Separation of Concerns ✅
- [x] UI logic in renderer.py
- [x] No UI code in main.py
- [x] Clean boundaries

#### 5.3. Living AI Principles
- [ ] Brain (Model) immutable
- [ ] Organism (Code) evolvable
- [ ] Flame creates rhythm
- [ ] No hardcoded behavior

#### 5.4. Safety
- [ ] Tool sandbox enforced
- [ ] HMAC verification active
- [ ] Protected files respected
- [ ] Offline-first maintained

---

### Phase 6: Documentation

#### 6.1. Core Docs
- [ ] **README.md** - Up to date?
- [ ] **DEV_GUIDE.md** - Up to date?
- [ ] **ARCHITECTURE.md** - Up to date?
- [ ] **PROJECT_STATUS.md** - Up to date?

#### 6.2. Spec Docs
- [ ] **NDJSON_SPEC.md** - Accurate?
- [ ] **DUAL_BRAIN_SPEC.md** - Accurate?
- [ ] **MANIFESTO.md** - Still relevant?

#### 6.3. User Guides
- [ ] **docs/USER_GUIDE_VI.md** - Current?
- [ ] **docs/evolution_system.md** - Accurate?

#### 6.4. New Docs
- [x] **docs/UI_REFACTORING.md** - Created
- [x] **docs/FIX_DUPLICATE_TEMPERATURE.md** - Created

---

## 🔧 Audit Execution Plan

### Step 1: Code Integrity Check (30 min)
```bash
# Compile all Python files
python -m compileall src/witness_forge -q

# Check imports
python -c "from witness_forge.agent.witness import WitnessAgent; print('✓ witness')"
python -c "from witness_forge.ui.renderer import StreamRenderer; print('✓ renderer')"
python -c "from witness_forge.forge.loader import ForgeLoader; print('✓ loader')"
# ... etc for all major modules
```

### Step 2: Test Suite Run (20 min)
```bash
# Run full test suite
python -m pytest tests/ -v --tb=short

# Check coverage
python -m pytest tests/ --cov=src/witness_forge --cov-report=html
```

### Step 3: Feature Verification (40 min)
```bash
# Test NDJSON output
python -m witness_forge chat --config config.yaml
# → Enter query, check NDJSON events in terminal

# Test dual-brain (if configured)
# → Check analysis (cyan) + final (green) separation

# Test evolution
# → Multiple queries, watch temperature changes

# Test memory
# → /mem commands, /mem graph, /mem find

# Test tools
# → /tool commands if allowed
```

### Step 4: Config Validation (15 min)
```bash
# Validate schema
python -c "from witness_forge.config import ConfigManager; c = ConfigManager('config.yaml'); print('✓ Valid')"

# Check all sections load
python scripts/check_config.py  # Create this script
```

### Step 5: Documentation Review (30 min)
- Read each doc
- Compare with actual code
- Note discrepancies
- Create update list

### Step 6: Report Generation (15 min)
- Compile findings
- Create status report
- Flag issues
- Recommend updates

---

## 📊 Audit Report Template

```markdown
# Project Audit Report - [Date]

## Executive Summary
- Overall Status: [PASS/FAIL/WARNINGS]
- Code Integrity: [%]
- Test Coverage: [%]
- Documentation Accuracy: [%]

## Findings

### ✅ Working Correctly
- [List features/components]

### ⚠️ Needs Attention
- [List issues]

### ❌ Broken/Missing
- [List critical issues]

## Recommendations
1. [Immediate fixes]
2. [Short-term improvements]
3. [Long-term enhancements]

## Documentation Updates Required
- [List docs to update]
- [Specific sections to change]
```

---

## 🎯 Success Criteria

### Must Pass:
- [ ] All Python files compile without errors
- [ ] Core tests pass (>80%)
- [ ] NDJSON output valid
- [ ] UI metrics display correctly
- [ ] Config loads without errors

### Should Pass:
- [ ] Full test suite >90%
- [ ] Dual-brain works
- [ ] Evolution triggers
- [ ] Memory persists
- [ ] Tools execute safely

### Nice to Have:
- [ ] 100% test coverage
- [ ] All docs 100% accurate
- [ ] Zero deprecation warnings
- [ ] Performance benchmarks met

---

## 📝 Next Steps After Audit

1. **Generate Report** - Consolidate findings
2. **Fix Critical Issues** - Address blockers
3. **Update Documentation** - Sync docs with reality
4. **Update PROJECT_STATUS.md** - Reflect current state
5. **Create CHANGELOG.md** - Document recent changes
6. **Tag Version** - If major milestone reached

---

## 🔗 Related Files

- `WITNESS_FORGE_AUDIT_REPORT.md` - Previous audit (historical)
- `PROJECT_STATUS.md` - Current project status
- `docs/DOCUMENTATION_AUDIT.md` - Doc-specific audit
- `ARCHITECTURE.md` - System architecture
- `DEV_GUIDE.md` - Developer guide
