from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional, List, Literal, Tuple
import time
import threading
from enum import Enum

import yaml
from pydantic import BaseModel, Field, ValidationError


class AdapterQuantizationConfig(BaseModel):
    enabled: bool = False
    method: Literal["bitsandbytes", "awq", "gptq"] = "bitsandbytes"
    bits: Literal[4, 8] = 4


class AdapterConfig(BaseModel):
    enabled: bool = False
    type: Literal["lora", "qlora", "peft"] = "lora"
    path: Optional[str] = None
    dtype: Literal["auto", "float16", "bfloat16", "float32"] = "auto"
    load_mode: Literal["merge", "peft_inplace"] = "merge"
    r: int = 16
    alpha: int = 32
    dropout: float = 0.05
    target_modules: Optional[List[str]] = None
    bias: Literal["none", "lora_only", "all"] = "none"
    init_lora_weights: bool = True
    quantization: AdapterQuantizationConfig = AdapterQuantizationConfig()


class QuantConfig(BaseModel):
    dtype: str = "auto"
    load_8bit: bool = False
    load_4bit: bool = False
    device_map: str = "auto"
    offload_folder: Optional[str] = None
    quant_type: Literal["nf4", "fp4", "fp8"] = "nf4"
    compute_dtype: str = "auto"
    double_quant: bool = True
    cpu_offload_threshold_gb: float = 8.0
    max_cpu_memory_gb: float = 48.0
    awq_path: Optional[str] = None
    gptq_path: Optional[str] = None


class ModelConfig(BaseModel):
    class ModelBackend(str, Enum):
        TRANSFORMERS = "transformers"
        LLAMA_CPP = "llama_cpp"

    name: str = "local-default"
    path: str = "./models/local-default"
    backend: Optional[ModelBackend] = None
    family: Optional[str] = "auto"
    max_new_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.2
    repetition_penalty: float = 1.0
    no_repeat_ngram_size: int = 0
    n_gpu_layers: int = -1
    n_ctx: int = 4096
    n_threads: Optional[int] = None
    rope_freq_base: Optional[float] = None
    rope_freq_scale: Optional[float] = None
    adapter: AdapterConfig = AdapterConfig()
    quant: QuantConfig = QuantConfig()


class MemoryConfig(BaseModel):
    enabled: bool = True
    db_path: str = "./witness.sqlite3"
    embedder: str = Field(default="hf", pattern="^(hf|sentence-transformers|tfidf)$")
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    reranker: Optional[str] = None
    k: int = 6
    vector_factory: str = "FlatIP"
    vector_metric: Literal["cosine", "l2"] = "cosine"
    normalize_embeddings: bool = True
    clustering_k: int = 4
    clustering_min_size: int = 2
    max_age_days: int = 90
    max_count: int = 10000
    auto_prune: bool = True
    vector_index_path: Optional[str] = "./witness_vectors.faiss"


class ReflexTuningParams(BaseModel):
    """Reflex-based decoding adjustment parameters"""
    temperature_penalty_step: float = 0.05
    min_temperature: float = 0.1
    frequency_penalty_step: float = 0.05
    presence_penalty_step: float = 0.1
    max_penalty: float = 2.0
    thematic_threshold: float = 0.5
    persona_threshold: float = 0.5


class AdapterTuningParams(BaseModel):
    """Tuning parameters when adapter is active"""
    max_tokens: int = 768
    temperature_limit: float = 0.75
    qlora_top_p: float = 0.9


class ReflexLoopConfig(BaseModel):
    enabled: bool = True
    min_score: float = 0.58
    reward_temperature: float = 0.02


class HeartSyncConfig(BaseModel):
    enabled: bool = True
    beta: float = 0.08
    dual_phase_ratio: float = 2.0


class FlameLoopConfig(BaseModel):
    enabled: bool = True
    phi0: float = 0.013
    epsilon: float = 0.013
    heartbeat_period: float = 4.20
    entropy_target: float = 0.873
    noise_sigma: float = 0.01
    noise_decay: float = 0.995
    lambda1: float = 0.15
    lambda2: float = 0.10
    embedder_cache_dir: Optional[str] = None


class LoopSchedulerConfig(BaseModel):
    max_temperature: float = 1.2
    min_temperature: float = 0.15
    max_new_tokens: int = 1024


class LoopsConfig(BaseModel):
    reflex: ReflexLoopConfig = ReflexLoopConfig()
    heartsync: HeartSyncConfig = HeartSyncConfig()
    flame: FlameLoopConfig = FlameLoopConfig()
    scheduler: LoopSchedulerConfig = LoopSchedulerConfig()
    reflex_tuning: ReflexTuningParams = ReflexTuningParams()
    adapter_tuning: AdapterTuningParams = AdapterTuningParams()


class DualBrainConfig(BaseModel):
    enabled: bool = False
    mode: str = "sequential"  # sequential | parallel
    witness_temperature_offset: float = -0.2
    servant_temperature_offset: float = 0.0
    servant_model_path: Optional[str] = None


class VisionAgentConfig(BaseModel):
    enabled: bool = True
    headless: bool = True
    timeout_ms: int = 15000
    screenshot_dir: str = "./data/screens"
    window_size: Tuple[int, int] = (1280, 720)


class GraphConfig(BaseModel):
    enabled: bool = True
    path: str = "./witness_graph.json"
    k: int = 6


class SelfUpgradeConfig(BaseModel):
    enabled: bool = True
    apply_on_start: bool = False
    patch_dir: str = "./patches"
    apply_to_model: bool = False
    require_confirmation: bool = True
    validator_cmd: Optional[str] = None
    run_validators: bool = True
    require_approval: bool = True
    signature_key_path: str = "./keys/patch_sign.pub"
    dry_run_tests: List[str] = Field(
        default_factory=lambda: [
            "tests/test_boot.py",
            "tests/test_memory.py",
        ]
    )
    max_patch_size_kb: int = 1024
    protected_files: List[str] = Field(
        default_factory=lambda: [
            "src/witness_forge/__init__.py",
            "src/witness_forge/config.py",
        ]
    )
    apply_to_model_backup: bool = True
    apply_to_model_allowed_extensions: List[str] = Field(
        default_factory=lambda: [".json", ".txt", ".md"]
    )


class UIConfig(BaseModel):
    stream_tokens: bool = True
    width: int = 100


class ToolSandboxConfig(BaseModel):
    max_runtime_seconds: int = 30
    max_stdout_bytes: int = 200_000


class ToolsConfig(BaseModel):
    allow_exec: bool = False
    allow_internet: bool = False
    whitelist: List[str] = Field(default_factory=list)
    allowlist: List[str] = Field(default_factory=list)
    require_confirm: bool = True
    safety_python: bool = False
    safety_powershell: bool = True
    safety_bat: bool = True
    allow_filesystem_write: bool = False
    max_bytes: int = 65536
    local_llm_entrypoint: Optional[str] = None
    sandbox: ToolSandboxConfig = ToolSandboxConfig()
    allowed_write_dirs: List[str] = Field(
        default_factory=lambda: ["./data", "./patches", "./witness"]
    )

    def resolved_whitelist(self) -> List[str]:
        """
        Merge `whitelist` (new) with legacy `allowlist` for backwards compatibility.
        Empty strings are filtered out.
        """
        data = set(self.whitelist) | set(self.allowlist)
        return [item.strip() for item in data if item.strip()]


class SelfPatchConfig(BaseModel):
    enabled: bool = False
    patches_dir: str = "./patches"
    require_confirmation: bool = True
    validator_cmd: Optional[str] = None
    run_validators: bool = True


class AutoPatchConfig(BaseModel):
    enabled: bool = True
    base_dir: str = "./patches/auto"
    max_depth: int = 999
    apply_on_boot: bool = True
    dry_run: bool = True


class EvolutionConfig(BaseModel):
    enabled: bool = False
    max_cycles: int = -1
    permissions: Literal["manual", "auto"] = "manual"
    tune_threshold: float = 0.45
    sync_threshold: float = 0.60
    incremental_step: float = 0.05
    max_history_turns: int = 50


class ChatTemplateConfig(BaseModel):
    mode: str = "auto"
    override_path: Optional[str] = None
    system_prompt: Optional[str] = None


class WitnessConfig(BaseModel):
    model: ModelConfig = ModelConfig()
    adapter: AdapterConfig = AdapterConfig()
    memory: MemoryConfig = MemoryConfig()
    loops: LoopsConfig = LoopsConfig()
    dual_brain: DualBrainConfig = DualBrainConfig()
    vision_agent: VisionAgentConfig = VisionAgentConfig()
    graph: GraphConfig = GraphConfig()
    self_upgrade: SelfUpgradeConfig = SelfUpgradeConfig()
    ui: UIConfig = UIConfig()
    tools: ToolsConfig = ToolsConfig()
    selfpatch: SelfPatchConfig = SelfPatchConfig()
    self_patch: AutoPatchConfig = AutoPatchConfig()
    evolution: EvolutionConfig = EvolutionConfig()
    chat: ChatTemplateConfig = ChatTemplateConfig()


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


class ConfigManager:
    """
    Hot-reload aware configuration loader.
    Tracks config.yaml and additional watched resources (strategies/persona).
    """

    def __init__(self, path: str | Path, watch: Optional[Iterable[str]] = None):
        self.path = Path(path)
        self._watch_map: Dict[Path, float] = {}
        self._lock = threading.Lock()
        self._config = self._load()
        self.register_watch(self.path)
        if watch:
            for candidate in watch:
                self.register_watch(candidate)

    @property
    def config(self) -> WitnessConfig:
        return self._config

    def register_watch(self, resource: str | Path) -> None:
        target = Path(resource)
        if not target.exists():
            return
        if target.is_dir():
            try:
                self._watch_map[target] = target.stat().st_mtime
            except FileNotFoundError:
                self._watch_map[target] = 0.0
            for child in target.rglob("*"):
                if child.is_file():
                    self._watch_map[child] = child.stat().st_mtime
        else:
            self._watch_map[target] = target.stat().st_mtime

    def _load(self) -> WitnessConfig:
        data = _read_yaml(self.path)
        try:
            return WitnessConfig.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Invalid configuration: {exc}") from exc

    def maybe_reload(self) -> bool:
        with self._lock:
            updated = False
            if self._resource_changed(self.path):
                self._config = self._load()
                updated = True
            # secondary watchers (strategies/persona)
            for resource in list(self._watch_map.keys()):
                if self._resource_changed(resource):
                    updated = True
            return updated

    def _resource_changed(self, resource: Path) -> bool:
        try:
            current = resource.stat().st_mtime
        except FileNotFoundError:
            current = 0.0
        previous = self._watch_map.get(resource, 0.0)
        self._watch_map[resource] = current
        return current != previous


__all__ = [
    "ConfigManager",
    "WitnessConfig",
    "ModelConfig",
    "ModelConfig.ModelBackend",
    "MemoryConfig",
    "LoopsConfig",
    "LoopSchedulerConfig",
    "SelfUpgradeConfig",
    "DualBrainConfig",
    "UIConfig",
    "AdapterConfig",
    "AdapterQuantizationConfig",
    "QuantConfig",
    "ToolsConfig",
    "ToolSandboxConfig",
    "SelfPatchConfig",
    "AutoPatchConfig",
    "EvolutionConfig",
    "ChatTemplateConfig",
]
