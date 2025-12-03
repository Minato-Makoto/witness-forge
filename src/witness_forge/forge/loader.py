from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import warnings

import logging
import os
import threading
import importlib
from pathlib import Path
import json

import torch
from transformers import (
    AutoConfig,
    AutoModelForCausalLM,
    AutoTokenizer,
    TextIteratorStreamer,
)

try:  # transformers >= 4.57
    from transformers import AutoModelForImageTextToText
except ImportError:  # pragma: no cover - fallback for older versions
    AutoModelForImageTextToText = None  # type: ignore[misc]
try:
    from transformers import AutoModelForVision2Seq
except ImportError:  # pragma: no cover
    AutoModelForVision2Seq = None  # type: ignore[misc]

try:  # optional quant helpers
    from transformers import BitsAndBytesConfig
except ImportError:  # pragma: no cover - optional
    BitsAndBytesConfig = None  # type: ignore[assignment]

try:  # GPTQ loader (optional)
    from auto_gptq import AutoGPTQForCausalLM
except ImportError:  # pragma: no cover - optional
    AutoGPTQForCausalLM = None  # type: ignore[assignment]

from ..config import ModelConfig, WitnessConfig
from .adapter_manager import apply_adapter_if_configured
from .chat_templates import detect_family
from .wrapper import LLMModel

log = logging.getLogger(__name__)


class ForgeLoader:
    """
    Load HuggingFace backbones with optional quantization + adapters.
    Handles CPU-offload heuristics for constrained VRAM targets (Win11 + 3070Ti focus).
    """

    @staticmethod
    def _map_arch_to_family(arch: str) -> str:
        arch = arch.lower()
        if "llama" in arch:
            return "llama"
        if "gptj" in arch or "gpt-j" in arch:
            return "gpt-j"
        if "gpt" in arch:
            return "gpt"
        if "qwen" in arch:
            return "qwen"
        if "mistral" in arch:
            return "mistral"
        if "gemma" in arch:
            return "gemma"
        return "auto"

    @staticmethod
    def load_model(
        model_cfg: ModelConfig,
        *,
        adapter_override_path: Optional[str] = None,
        dry_run: bool = False,
        witness_cfg: Optional[WitnessConfig] = None,
    ) -> Tuple[Any, Any, Any]:
        path = model_cfg.path
        if dry_run:
            return ForgeLoader._mock()

        backend = ForgeLoader._detect_backend(model_cfg)
        if backend == ModelConfig.ModelBackend.LLAMA_CPP:
            if not Path(path).exists():
                raise FileNotFoundError(path)
            try:
                return ForgeLoader._load_llama_cpp(model_cfg, witness_cfg=witness_cfg)
            except Exception as exc:
                log.error(
                    "Load GGUF bằng llama-cpp thất bại, fallback Transformers nếu có. Lý do: %s",
                    exc,
                    exc_info=exc,
                )
                if not os.path.isdir(path):
                    raise
                backend = ModelConfig.ModelBackend.TRANSFORMERS

        if not os.path.isdir(path):
            if os.path.isfile(path):
                 # If it's a file but not GGUF (handled above), warn or error.
                 # Transformers *can* load from single file (e.g. .pt), but usually it's a mistake in this context.
                 if not str(path).endswith((".pt", ".bin", ".safetensors")):
                     log.warning(f"Model path is a file but not GGUF/pt/bin/safetensors: {path}. Load might fail.")
            else:
                 # Not a dir, not a file.
                 raise FileNotFoundError(f"Model path not found: {path}")

        # Prepare path to possible config.json for fallback
        cfg_path = Path(path) / "config.json"
        config = None  # Ensure variable exists even if AutoConfig fails
        # Try to load model config via transformers AutoConfig
        try:
            config = AutoConfig.from_pretrained(path, local_files_only=True)
            model_type = getattr(config, "model_type", "")
        except Exception:
            # Fallback: manually read config.json if present
            if cfg_path.is_file():
                try:
                    with cfg_path.open("r", encoding="utf-8") as f:
                        cfg_json = json.load(f)
                    model_type = cfg_json.get("model_type", "")
                except Exception:
                    model_type = ""
            else:
                model_type = ""
        
        # Smart detection for Transformers (family)
        if model_cfg.family in {None, "", "auto"}:
            detected = ForgeLoader._map_arch_to_family(model_type)
            if detected != "auto":
                log.info(f"Auto-detected family '{detected}' from model_type '{model_type}'")
                model_cfg.family = detected

        # Auto-detect n_ctx if not explicitly set (use 0 or -1 as sentinel)
        if model_cfg.n_ctx in {0, -1}:
            # Prefer max_position_embeddings from config if available
            max_pos = getattr(config, "max_position_embeddings", None) if config is not None else None
            if max_pos:
                model_cfg.n_ctx = max_pos
                log.info(f"Auto-set n_ctx to {max_pos} from model config")
            else:
                # Try to read from config.json as fallback
                if cfg_path.is_file():
                    try:
                        with cfg_path.open("r", encoding="utf-8") as f:
                            cfg_json = json.load(f)
                        max_pos = cfg_json.get("max_position_embeddings")
                        if max_pos:
                            model_cfg.n_ctx = max_pos
                            log.info(f"Auto-set n_ctx to {max_pos} from config.json")
                    except Exception:
                        pass

        tok = AutoTokenizer.from_pretrained(path, local_files_only=True)
        kwargs: Dict[str, Any] = {}
        target_device: Optional[str] = None
        quant = model_cfg.quant

        dm = (quant.device_map or "auto").lower()
        if dm == "auto":
            kwargs["device_map"] = "auto"
        elif dm in {"cuda", "gpu"}:
            target_device = "cuda" if torch.cuda.is_available() else "cpu"
        elif dm == "cpu":
            target_device = "cpu"
        elif dm:
            kwargs["device_map"] = quant.device_map

        resolved_dtype = ForgeLoader._resolve_dtype(quant.dtype, ForgeLoader._auto_dtype())
        if resolved_dtype is not None:
            kwargs["dtype"] = resolved_dtype

        quantization_cfg = ForgeLoader._build_bnb_config(quant)
        if quantization_cfg:
            warnings.filterwarnings(
                "ignore",
                message="MatMul8bitLt: inputs will be cast",
                module="bitsandbytes",
            )
            kwargs["quantization_config"] = quantization_cfg
        else:
            if quant.load_8bit:
                kwargs["load_in_8bit"] = True
            if quant.load_4bit:
                kwargs["load_in_4bit"] = True
        if quant.offload_folder:
            kwargs["offload_folder"] = quant.offload_folder

        ForgeLoader._maybe_enable_cpu_offload(kwargs, quant)

        model_loader = AutoModelForCausalLM
        if quant.gptq_path:
            if AutoGPTQForCausalLM is None:
                raise RuntimeError("Cần cài auto-gptq để load mô hình GPTQ.")
            model_loader = AutoGPTQForCausalLM  # type: ignore[assignment]
            path = quant.gptq_path
            kwargs.setdefault("use_safetensors", True)
            kwargs.setdefault("trust_remote_code", True)
        elif model_type in {"qwen3_vl", "qwen3_vl_moe", "qwen2_vl"}:
            if AutoModelForImageTextToText is not None:
                model_loader = AutoModelForImageTextToText  # type: ignore[assignment]
            elif AutoModelForVision2Seq is not None:
                model_loader = AutoModelForVision2Seq  # type: ignore[assignment]

        mdl = model_loader.from_pretrained(path, local_files_only=True, **kwargs)
        if target_device:
            mdl.to(target_device)
        elif (
            "device_map" not in kwargs
            and torch.cuda.is_available()
            and not quant.load_8bit
            and not quant.load_4bit
        ):
            mdl.to("cuda")
        mdl.eval()

        cfg_source = witness_cfg if witness_cfg is not None else model_cfg
        mdl, adapter_status = apply_adapter_if_configured(
            mdl,
            cfg_source,
            adapter_override_path=adapter_override_path,
        )
        if adapter_status.enabled:
            log.info("Đã gắn adapter %s (%s)", adapter_status.path, adapter_status.note)
        else:
            log.debug("Adapter skipped: %s", adapter_status.note)

        def generate_fn(prompt: str, gen: Dict[str, float]):
            if hasattr(mdl, "device"):
                device = mdl.device
            else:
                try:
                    device = next(mdl.parameters()).device  # type: ignore[attr-defined]
                except (StopIteration, AttributeError):
                    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            encoded = tok(prompt, return_tensors="pt")
            if hasattr(encoded, "to"):
                encoded = encoded.to(device)
            batch = encoded if isinstance(encoded, dict) else {k: v for k, v in encoded.items()}
            rep_penalty = float(gen.get("repetition_penalty", 1.0))
            ngram_block = int(gen.get("no_repeat_ngram_size", 0))
            gen_args: Dict[str, Any] = {
                "max_new_tokens": int(gen.get("max_new_tokens", 256)),
                "do_sample": True,
                "temperature": float(gen.get("temperature", 0.7)),
                "top_p": float(gen.get("top_p", 0.9)),
                "repetition_penalty": max(1.0, rep_penalty),
            }
            if ngram_block > 0:
                gen_args["no_repeat_ngram_size"] = ngram_block

            pad_token_id = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
            if pad_token_id is not None and "pad_token_id" not in gen_args:
                gen_args["pad_token_id"] = pad_token_id

            # Keep special tokens (tags) for UI formatting - they'll be parsed by _format_for_display
            streamer = TextIteratorStreamer(tok, skip_special_tokens=False, skip_prompt=True)
            generate_kwargs = {**batch, **gen_args, "streamer": streamer}

            thread = threading.Thread(target=mdl.generate, kwargs=generate_kwargs)
            thread.start()
            try:
                for text in streamer:
                    if text:
                        yield text
            finally:
                thread.join()

        return tok, mdl, generate_fn

    @staticmethod
    def _detect_backend(model_cfg: ModelConfig) -> ModelConfig.ModelBackend:
        if model_cfg.backend:
            return model_cfg.backend
        candidate = Path(model_cfg.path)
        if candidate.is_file() and candidate.suffix.lower() == ".gguf":
            return ModelConfig.ModelBackend.LLAMA_CPP
        if candidate.is_dir():
            for child in candidate.iterdir():
                if child.suffix.lower() == ".gguf":
                    return ModelConfig.ModelBackend.LLAMA_CPP
        return ModelConfig.ModelBackend.TRANSFORMERS

    @staticmethod
    def _load_llama_cpp(model_cfg: ModelConfig, *, witness_cfg: Optional[WitnessConfig] = None) -> Tuple[Any, Any, Any]:
        try:
            llama_mod = importlib.import_module("llama_cpp")
        except ImportError as exc:  # pragma: no cover - optional path
            raise RuntimeError("Thiếu llama-cpp-python. Cài bằng: pip install .[gguf]") from exc
        Llama = getattr(llama_mod, "Llama", None)
        if Llama is None:  # pragma: no cover - defensive
            raise RuntimeError("llama_cpp.Llama không khả dụng trong bản cài đặt hiện tại.")

        model_path = Path(model_cfg.path).resolve()
        if model_path.is_dir():
            ggufs = sorted(model_path.glob("*.gguf"))
            if not ggufs:
                raise FileNotFoundError(f"Không tìm thấy file .gguf trong {model_path}")
            model_path = ggufs[0]
        if not model_path.is_file():
            raise FileNotFoundError(f"Không tìm thấy file GGUF: {model_path}")

        kwargs: Dict[str, Any] = {
            "model_path": str(model_path),
            "n_gpu_layers": model_cfg.n_gpu_layers,
            "verbose": False,
            "logits_all": False,
        }
        initial_family: Optional[str] = None
        if model_cfg.family and model_cfg.family not in {"", "auto"}:
            initial_family = model_cfg.family
        else:
            fname_guess = ForgeLoader._map_arch_to_family(model_path.name)
            if fname_guess != "auto":
                initial_family = fname_guess
        if initial_family:
            kwargs["model_type"] = initial_family
        
        # Auto-detect n_ctx from GGUF metadata BEFORE loading model
        # NOTE: GGUFReader may fail if GGUF file uses newer quantization types (e.g., MXFP4/type 39)
        # that are not supported by the installed gguf library version.
        # Current gguf 0.17.1 supports up to type 35. Upgrade gguf if you encounter errors.
        if model_cfg.n_ctx in {0, -1}:
            try:
                from gguf import GGUFReader
                # GGUFReader constructor parses all tensors - will fail if tensor quant type is unsupported
                reader = GGUFReader(str(model_path))
                
                # Get architecture to find the correct context_length key
                arch = "llama"  # Default fallback
                try:
                    arch_field = reader.fields.get("general.architecture")
                    if arch_field and arch_field.parts:
                        raw_arch = arch_field.parts[-1]
                        if hasattr(raw_arch, 'tobytes'):
                            arch = raw_arch.tobytes().decode("utf-8")
                        elif isinstance(raw_arch, (str, bytes)):
                            arch = str(raw_arch) if isinstance(raw_arch, str) else raw_arch.decode("utf-8")
                except (AttributeError, UnicodeDecodeError, IndexError):
                    pass  # Use fallback
                
                keys_to_try = [
                    f"{arch}.context_length",
                    "llama.context_length",
                    "general.context_length"
                ]

                ctx_length = None
                for key in keys_to_try:
                    if key in reader.fields:
                        try:
                            field = reader.fields[key]
                            raw_val = field.parts[-1] if field.parts else None
                            if raw_val is not None:
                                if isinstance(raw_val, (list, tuple)):
                                    ctx_length = int(raw_val[0])
                                else:
                                    ctx_length = int(raw_val)
                                log.info(f"Found n_ctx in GGUF metadata key: {key} = {ctx_length}")
                                break
                        except (ValueError, TypeError, IndexError):
                            continue
                
                if ctx_length:
                    detected_ctx = ctx_length
                    # Cap n_ctx to prevent OOM on consumer hardware (131k is too big for 3070 Ti)
                    SAFE_CTX_LIMIT = 8192
                    if detected_ctx > SAFE_CTX_LIMIT:
                        log.warning(f"Auto-detected n_ctx={detected_ctx} is too large for typical VRAM. Capping at {SAFE_CTX_LIMIT}.")
                        detected_ctx = SAFE_CTX_LIMIT
                    
                    kwargs["n_ctx"] = detected_ctx
                    model_cfg.n_ctx = detected_ctx
                    log.info(f"Auto-set n_ctx to {detected_ctx} from GGUF metadata")
                else:
                    kwargs["n_ctx"] = 8192
                    model_cfg.n_ctx = 8192
                    log.warning(f"Could not auto-detect n_ctx from GGUF metadata (tried {keys_to_try}), using default: 8192")
            except Exception as e:
                # Most common error: "np.uint32(39) is not a valid GGMLQuantizationType"
                # This means the GGUF file uses a newer quantization type (e.g., MXFP4)
                # that the installed gguf library doesn't support.
                # Solution: pip install --upgrade gguf
                error_msg = str(e)
                if "GGMLQuantizationType" in error_msg:
                    log.warning(
                        f"GGUF metadata reading failed: {e}\n"
                        "Your GGUF file uses a newer quantization type not supported by gguf 0.17.1 (latest on PyPI).\n"
                        "The auto-detection feature requires a newer gguf version from llama.cpp source.\n"
                        "Using safe default n_ctx: 8192\n"
                        "To use a different context size, set 'n_ctx' explicitly in config.yaml"
                    )
                else:
                    log.warning(f"Failed to read GGUF metadata for n_ctx auto-detection: {e}, using default: 8192")
                kwargs["n_ctx"] = 8192
                model_cfg.n_ctx = 8192
        else:
            kwargs["n_ctx"] = model_cfg.n_ctx
        
        if model_cfg.rope_freq_base is not None:
            kwargs["rope_freq_base"] = model_cfg.rope_freq_base
        if model_cfg.rope_freq_scale is not None:
            kwargs["rope_freq_scale"] = model_cfg.rope_freq_scale
        if model_cfg.n_threads is not None:
            kwargs["n_threads"] = model_cfg.n_threads
        

        try:
            llm = Llama(**kwargs)
        except Exception as exc:  # pragma: no cover - heavy path
            raise RuntimeError(
                f"Không load được GGUF tại {model_path}. "
                "Kiểm tra file có tồn tại/đọc được, phiên bản llama-cpp-python tương thích (CPU/GPU), "
                "và đủ RAM/VRAM. Chi tiết: "
                f"{exc}"
            ) from exc

        # Smart detection for GGUF
        if model_cfg.family in {None, "", "auto"}:
            meta = getattr(llm, "metadata", {})
            arch = meta.get("general.architecture", "")
            if arch:
                detected = ForgeLoader._map_arch_to_family(str(arch))
                if detected != "auto":
                    log.info(f"Auto-detected family '{detected}' from GGUF architecture '{arch}'")
                    model_cfg.family = detected
            else:
                # Fallback: try to guess from filename if metadata is missing
                fname = Path(model_path).name.lower()
                detected = ForgeLoader._map_arch_to_family(fname)
                if detected != "auto":
                    log.info(f"Auto-detected family '{detected}' from filename '{fname}'")
                    model_cfg.family = detected

        gpu_support = getattr(llama_mod, "llama_gpu_support", None)
        if callable(gpu_support):
            try:
                if not gpu_support() and model_cfg.n_gpu_layers != 0:
                    log.warning("llama-cpp build không có GPU/cuBLAS; cân nhắc giảm n_gpu_layers hoặc cài bản CUDA.")
            except Exception:
                pass

        class _Tok:
            def __init__(self, model_path_str, model_name=None):
                self.model_path = model_path_str
                self.name_or_path = model_name or model_path_str
                
            def __call__(self, prompt, return_tensors=None):
                return {"prompt": prompt}

            def decode(self, ids, skip_special_tokens=True):
                return str(ids)

        def generate_fn(prompt: str, gen: Dict[str, float]):
            # Only use true template end tokens to avoid cutting off reasoning/content
            # DO NOT add structural tags like <|start|>, <|channel|> here - it breaks the flow!
            default_stops = [
                "<|im_end|>",
                "<|eot_id|>",
                # "<|end|>", # Managed dynamically by witness.py based on role
            ]
            user_stops = gen.get("stop") or []
            all_stops = default_stops + (user_stops if isinstance(user_stops, list) else [user_stops])
            
            completion_kwargs = {
                "prompt": prompt,
                "max_tokens": int(gen.get("max_new_tokens", 256)),
                "temperature": float(gen.get("temperature", 0.7)),
                "top_p": float(gen.get("top_p", 0.9)),
                "repeat_penalty": float(gen.get("repetition_penalty", 1.0)),
                "stream": True,
                "stop": all_stops,
            }
            stream = llm.create_completion(**completion_kwargs)
            
            for chunk in stream:
                choices = chunk.get("choices") or [{}]
                if choices:
                    finish_reason = choices[0].get("finish_reason")
                    if finish_reason in ("stop", "length"):
                        break
                text = choices[0].get("text", "") or ""
                if text:
                    yield text


        return _Tok(str(model_path), model_cfg.name), llm, generate_fn

    @staticmethod
    def _mock() -> Tuple[Any, Any, Any]:
        class _Tok:
            def __call__(self, x, return_tensors=None):
                return {"input_ids": None}

            def decode(self, ids, skip_special_tokens=True):
                return ""

        def generate_fn(prompt: str, gen: Dict[str, float]):
            yield " [MOCK] Add a local model in ./models and set config.yaml:model.path"

        return _Tok(), None, generate_fn

    @staticmethod
    def _resolve_dtype(option: str, fallback: torch.dtype) -> Optional[torch.dtype]:
        mapping = {
            "float32": torch.float32,
            "float16": torch.float16,
            "half": torch.float16,
            "bfloat16": torch.bfloat16,
        }
        if option == "auto":
            return fallback
        return mapping.get(option.lower()) if isinstance(option, str) else None

    @staticmethod
    def _auto_dtype() -> torch.dtype:
        if not torch.cuda.is_available():
            return torch.float32
        props = torch.cuda.get_device_properties(0)
        if getattr(props, "major", 0) >= 8:
            return torch.bfloat16
        return torch.float16

    @staticmethod
    def _gpu_vram_gb() -> float:
        if not torch.cuda.is_available():
            return 0.0
        props = torch.cuda.get_device_properties(0)
        return props.total_memory / (1024**3)

    @staticmethod
    def _build_bnb_config(quant_cfg) -> Optional[Any]:
        if BitsAndBytesConfig is None:
            return None
        if not (quant_cfg.load_4bit or quant_cfg.load_8bit):
            return None
        compute_dtype = ForgeLoader._resolve_dtype(
            quant_cfg.compute_dtype,
            ForgeLoader._auto_dtype(),
        )
        quant_type = (quant_cfg.quant_type or "nf4").upper()
        return BitsAndBytesConfig(
            load_in_8bit=quant_cfg.load_8bit,
            load_in_4bit=quant_cfg.load_4bit,
            bnb_4bit_use_double_quant=quant_cfg.double_quant,
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_quant_type=quant_type,
        )

    @staticmethod
    def _maybe_enable_cpu_offload(kwargs: Dict[str, Any], quant_cfg) -> None:
        if kwargs.get("device_map") not in {None, "auto"}:
            return
        vram = ForgeLoader._gpu_vram_gb()
        if not vram:
            return
        if vram <= quant_cfg.cpu_offload_threshold_gb:
            log.info("VRAM %.1fGB thấp, bật CPU-offload fallback.", vram)
            kwargs["device_map"] = "auto"
            kwargs["max_memory"] = {
                0: f"{max(1, int(vram) - 1)}GiB",
                "cpu": f"{int(quant_cfg.max_cpu_memory_gb)}GiB",
            }
