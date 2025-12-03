from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import List, Optional

import yaml
from rich.console import Console
from rich.prompt import Prompt

from .agent.flame_core import FlameParams
from .agent.evolution import EvolutionController
from .agent.loops import LoopConfig, Loops
from .agent.dual_brain import DualBrain
from .agent.model_loader import build_base_decode, load_brain, unload_model
from .agent.self_patch import AutoPatchEngine
from .agent.self_patch_manager import ControlledPatchManager
from .agent.self_upgrade import SelfUpgrade
from .agent.selfpatch import SelfPatchError, SelfPatchManager
from .agent.witness import WitnessAgent
from .config import ConfigManager, ModelConfig, WitnessConfig
from .config_overlay import ConfigOverlay
from .forge.chat_templates import ChatTemplateManager, detect_family
from .forge.loader import ForgeLoader
from .memory.embedding import build_embedder
from .memory.retrieval import Retriever, build_vocab_from_mem
from .memory.store import MemoryStore
from .memory.vector_store import VectorStore
from .memory.graph_rag import GraphMemory
from .memory.hybrid_retriever import HybridRetriever
from .agents.web_agent import VisionWebAgent
from .tools.dispatcher import ToolDispatcher
from .tools.runner import ToolRunner
from .ui.renderer import StreamRenderer

console = Console()


def _confirm_console(message: str) -> bool:
    answer = Prompt.ask(f"{message} (y/N)", choices=["y", "n", "Y", "N"], default="n")
    return answer.lower() == "y"


def _with_override(manager: ConfigManager, model_name: str) -> WitnessConfig:
    base_cfg = manager.config.model_copy(deep=True)
    if model_name:
        base_cfg.model.name = model_name

    overlay = ConfigOverlay(base_cfg, Path("patches/active_evolution.json"))
    cfg = overlay.apply()
    if model_name:
        cfg.model.name = model_name
    return _apply_model_patch_routes(cfg)


def _apply_model_patch_routes(cfg: WitnessConfig) -> WitnessConfig:
    if not cfg.self_upgrade.apply_to_model:
        return cfg
    model_root = Path(cfg.model.path).resolve()
    if model_root.is_file():
        model_root = model_root.parent
    selfpatch = cfg.selfpatch.model_copy(update={"patches_dir": str(model_root / "patches")})
    self_patch = cfg.self_patch.model_copy(update={"base_dir": str(model_root / "patches/auto")})
    # NOTE: We do NOT redirect self_upgrade (config patching) to model folder anymore.
    # Config is global, so its patch history must be global (./patches), not siloed per model.
    return cfg.model_copy(update={"selfpatch": selfpatch, "self_patch": self_patch})


def _loop_config(cfg: WitnessConfig) -> LoopConfig:
    return LoopConfig(
        reflex_min_score=cfg.loops.reflex.min_score,
        heart_beta=cfg.loops.heartsync.beta,
        flame_params=FlameParams(
            phi0=cfg.loops.flame.phi0,
            epsilon=cfg.loops.flame.epsilon,
            heartbeat_period=cfg.loops.flame.heartbeat_period,
            entropy_target=cfg.loops.flame.entropy_target,
            noise_sigma=cfg.loops.flame.noise_sigma,
            noise_decay=cfg.loops.flame.noise_decay,
            lambda1=cfg.loops.flame.lambda1,
            lambda2=cfg.loops.flame.lambda2,
        ),
        reward_temperature=cfg.loops.reflex.reward_temperature,
        max_temperature=cfg.loops.scheduler.max_temperature,
        min_temperature=cfg.loops.scheduler.min_temperature,
        max_new_tokens=cfg.loops.scheduler.max_new_tokens,
        reflex_tuning=cfg.loops.reflex_tuning,
        adapter_tuning=cfg.loops.adapter_tuning,
        flame_embedder_model=cfg.memory.embedding_model,
        flame_embedder_cache=cfg.loops.flame.embedder_cache_dir,
        flame_embedder_device=None,
    )


def run_chat(
    config_path: str,
    model_name: str = "",
    use_template: bool | None = None,
    *,
    allow_selfpatch: bool = False,
):
    manager = ConfigManager(config_path, watch=["strategies", "configs"])
    cfg = _with_override(manager, model_name)
    tool_runner = ToolRunner(
        cfg.tools,
        confirm_callback=_confirm_console,
        db_path=cfg.memory.db_path,
    )
    selfpatch = SelfPatchManager(
        cfg.selfpatch,
        allow_selfpatch=allow_selfpatch,
        confirm_callback=_confirm_console,
    )
    autopatch = AutoPatchEngine(
        cfg.self_patch,
        manager=selfpatch,
        confirm_callback=_confirm_console,
    )
    model_root = Path(cfg.model.path).resolve()
    if model_root.is_file():
        model_root = model_root.parent
    patch_dir_override = None
    targeted_copy = False
    if cfg.self_upgrade.apply_to_model:
        patch_dir_override = Path(cfg.self_upgrade.patch_dir).resolve()
        targeted_copy = True
    patch_controller = ControlledPatchManager(
        cfg.self_upgrade,
        repo_root=model_root if cfg.self_upgrade.apply_to_model else Path.cwd(),
        db_path=cfg.memory.db_path,
        patch_dir_override=patch_dir_override,
        targeted_copy=targeted_copy,
    )
    upgrade = SelfUpgrade(
        config_path,
        patch_dir=cfg.self_upgrade.patch_dir,
        selfpatch=selfpatch,
        upgrade_cfg=cfg.self_upgrade,
        controller=patch_controller,
        memory_db_path=cfg.memory.db_path,
    )
    evolution = EvolutionController(cfg.evolution, upgrade, autopatch, _confirm_console)

    if cfg.self_patch.apply_on_boot and not allow_selfpatch:
        console.print("[autopatch] ⚠️  apply_on_boot=True nhưng --allow-selfpatch=False. Bỏ qua auto-apply.", style="yellow")
    
    autopatch.apply_pending()

    state = {
        "agent": None,
        "store": None,
        "retr": None,
        "tok": None,
        "mdl": None,
        "gen_fn": None,
        "base_decode": {},
        "cfg": cfg,
        "dispatcher": None,
        "template_manager": None,
        "dual_brain": None,
        "servant_tok": None,
        "servant_mdl": None,
        "servant_gen_fn": None,
        "loop_info": "",
    }

    def build_memory_and_tools(cur_cfg: WitnessConfig, store: MemoryStore):
        vision_agent = None
        if getattr(cur_cfg, "vision_agent", None) and cur_cfg.vision_agent.enabled:
            vision_agent = VisionWebAgent(
                headless=cur_cfg.vision_agent.headless,
                timeout_ms=cur_cfg.vision_agent.timeout_ms,
                screenshot_dir=cur_cfg.vision_agent.screenshot_dir,
                window_size=cur_cfg.vision_agent.window_size,
                enable_screenshots=getattr(cur_cfg.vision_agent, "enable_screenshots", False),
            )
        dispatcher = ToolDispatcher(
            tool_runner,
            allow_python=cur_cfg.tools.safety_python,
            allow_powershell=cur_cfg.tools.safety_powershell,
            allow_bat=cur_cfg.tools.safety_bat,
            allow_filesystem_write=cur_cfg.tools.allow_filesystem_write,
            max_bytes=cur_cfg.tools.max_bytes,
            local_llm_entrypoint=cur_cfg.tools.local_llm_entrypoint,
            allowed_write_dirs=cur_cfg.tools.allowed_write_dirs,
            vision_agent=vision_agent,
        )
        dispatcher.set_internet_access(cur_cfg.tools.allow_internet)
        embedder = build_embedder(
            cur_cfg.memory.embedder,
            cur_cfg.memory.embedding_model,
            cache_folder=cur_cfg.loops.flame.embedder_cache_dir,
            device=None,
        )
        base_memories = store.recent_memories(512)
        if base_memories:
            embedder.fit(base_memories)
        else:
            # Fit with dummy data to avoid NotFittedError for TF-IDF
            embedder.fit(["initialization"])
        dim = getattr(embedder, "dimension", len(base_memories) or 384) or 384

        vector_store = None
        if cur_cfg.memory.enabled:
            vector_store = VectorStore(
                cur_cfg.memory.db_path,
                max(32, dim),
                factory=cur_cfg.memory.vector_factory,
                metric=cur_cfg.memory.vector_metric,
                normalize=cur_cfg.memory.normalize_embeddings,
            )
            store.attach_semantic_hook(embedder.embed, vector_store)
        base_retriever = Retriever(store, embedder, vector_store, k=cur_cfg.memory.k)
        graph_mem = GraphMemory(cur_cfg.graph.path) if getattr(cur_cfg, "graph", None) and cur_cfg.graph.enabled else None
        retriever = HybridRetriever(base_retriever, graph_mem, k=cur_cfg.memory.k)
        return retriever, dispatcher

    def rebuild_agent():
        # Explicitly unload previous model to free VRAM/RAM before loading new one
        if state["mdl"] is not None:
            console.print("[system] Unloading previous model...")
            unload_model(state["mdl"])
        if state.get("servant_mdl") is not None:
            console.print("[system] Unloading previous servant model...")
            unload_model(state["servant_mdl"])
        state.update(
            {
                "mdl": None,
                "gen_fn": None,
                "tok": None,
                "agent": None,
                "servant_mdl": None,
                "servant_gen_fn": None,
                "servant_tok": None,
                "dual_brain": None,
            }
        )

        manager.maybe_reload()
        cur = _with_override(manager, model_name)
        state["cfg"] = cur
        tool_runner.refresh(cur.tools)
        selfpatch.refresh(cur.selfpatch)
        autopatch.refresh(cur.self_patch)
        evolution.refresh(cur.evolution)
        if Path("patches/active_evolution.json").exists():
            console.print("[evolution] Active overlay detected - using evolved params", style="yellow")

        tok, mdl, gen_fn, base_decode = load_brain(cur.model, witness_cfg=cur)
        store = MemoryStore(cur.memory.db_path)
        retr, dispatcher = build_memory_and_tools(cur, store)
        vocab = build_vocab_from_mem(store.recent_memories(256), min_freq=2)
        loop_cfg = _loop_config(cur)
        active_adapter = cur.adapter if cur.adapter.enabled else cur.model.adapter
        adapter_mode = active_adapter.type if active_adapter.enabled else "none"
        loops = Loops(loop_cfg, vocab, adapter_mode=adapter_mode)

        def _loop_debug(tuned: dict, loop_state: dict | None) -> None:
            try:
                phase = (loop_state or {}).get("phase", {}) or {}
                base = (loop_state or {}).get("base_decode", {}) or {}
                state_tag = (loop_state or {}).get("state", "?")
                base_temp = base.get("temperature", "n/a")
                
                # Extract k and epsilon from phase
                k = phase.get("k", "n/a")
                epsilon = phase.get("epsilon", "n/a")
                
                # Format k and epsilon properly
                k_str = f"{k:.4f}" if isinstance(k, (int, float)) else str(k)
                epsilon_str = f"{epsilon:.4f}" if isinstance(epsilon, (int, float)) else str(epsilon)

                scores = (loop_state or {}).get("scores", {}) or {}
                reflex_score = scores.get("reflex_score", 0.0)

                patch_state = "base"
                patch_file = Path("patches/active_evolution.json")
                if patch_file.exists():
                    try:
                        data = json.loads(patch_file.read_text(encoding="utf-8"))
                        patch_state = data.get("state", "evolving")
                    except Exception:
                        patch_state = "evolving"
                
                info_str = (
                    f"Effective Temperature: {float(tuned.get('temperature', 0.0)):.3f} "
                    f"(top_p={float(tuned.get('top_p', 0.0)):.3f}, "
                    f"state={state_tag}, k={k_str}, "
                    f"ε={epsilon_str}, "
                    f"fast={phase.get('fast', 0.0):+.3f}, "
                    f"slow={phase.get('slow', 0.0):+.3f}, "
                    f"beta={(loop_state or {}).get('heart_beta', 'n/a')}, "
                    f"reflex={reflex_score:.3f}, "
                    f"evolution={patch_state})"
                )

                state["loop_info"] = info_str
            except Exception as exc:  # pragma: no cover - debug hook only
                console.print(f"[loop] debug log failed: {exc}", style="red")

        family = detect_family(cur.model.family or cur.model.name)
        template_mode = cur.chat.mode if cur.chat.mode != "auto" else family
        if use_template is False:
            template_mode = "manual"
        elif use_template is True and template_mode == "manual":
            template_mode = family
        template_manager = ChatTemplateManager(tok, template_mode)

        agent = WitnessAgent(
            tok,
            gen_fn,
            base_decode,
            loops,
            store,
            retr,
            template_manager=template_manager,
            tool_dispatcher=dispatcher,
            loop_observer=_loop_debug,
            brain_id="path1",
        )

        dual_brain = None
        servant_tok = None
        servant_mdl = None
        servant_gen_fn = None
        dual_cfg = getattr(cur, "dual_brain", None)
        dual_requested = bool(dual_cfg and (dual_cfg.enabled or dual_cfg.servant_model_path))
        force_dual = bool(dual_cfg and dual_cfg.enabled)
        if dual_requested:
            servant_decode = base_decode
            servant_path = dual_cfg.servant_model_path or ""
            if servant_path:
                console.print(f"[dual-brain] Loading servant model from {servant_path} ...")
                try:
                    servant_tok, servant_mdl, servant_gen_fn, servant_decode = load_brain(
                        cur.model,
                        witness_cfg=cur,
                        path_override=servant_path,
                        name_suffix="-servant",
                    )
                    console.print("[dual-brain] Servant model loaded.")
                except Exception as exc:
                    console.print(f"[dual-brain] Failed to load servant model, fallback to shared: {exc}", style="yellow")
                    servant_tok = servant_mdl = servant_gen_fn = None
            if servant_gen_fn is None:
                console.print("[dual-brain] Only one model available; using shared model.", style="yellow")
                servant_tok, servant_mdl, servant_gen_fn = tok, mdl, gen_fn
                servant_decode = base_decode

            witness_agent = WitnessAgent(
                tok,
                gen_fn,
                base_decode,
                loops,
                store,
                retr,
                template_manager=template_manager,
                tool_dispatcher=dispatcher,
                loop_observer=_loop_debug,
                role="witness",
                brain_id="path1",
                temperature_offset=dual_cfg.witness_temperature_offset,
            )

            if servant_gen_fn is None or servant_gen_fn is gen_fn:
                # Shared model: reuse the same agent instance to share history/state
                servant_agent = witness_agent
            else:
                servant_agent = WitnessAgent(
                    servant_tok,
                    servant_gen_fn,
                    servant_decode,
                    loops,
                    store,
                    retr,
                    template_manager=template_manager,
                    tool_dispatcher=dispatcher,
                    loop_observer=_loop_debug,
                    role="servant",
                    brain_id="path2",
                    temperature_offset=dual_cfg.servant_temperature_offset,
                )
            dual_brain = DualBrain(witness_agent, servant_agent, force_dual=force_dual)

        state.update(
            {
                "agent": agent,
                "store": store,
                "retr": retr,
                "tok": tok,
                "mdl": mdl,
                "gen_fn": gen_fn,
                "base_decode": base_decode,
                "dispatcher": dispatcher,
                "template_manager": template_manager,
                "dual_brain": dual_brain,
                "servant_tok": servant_tok,
                "servant_mdl": servant_mdl,
                "servant_gen_fn": servant_gen_fn,
            }
        )
        if mdl is None:
            console.print("[model] Mock generator active – thêm model local để tắt thông báo.")
        else:
            try:
                device = next(mdl.parameters()).device  # type: ignore[attr-defined]
            except (StopIteration, AttributeError):
                device = getattr(mdl, "device", "unknown")
            console.print(f"[model] Loaded {cur.model.name} on {device}.")

    rebuild_agent()
    console.print("Commands: /mem [graph|find|clear], /save, /reset, /reload, /eval, /upgrade, /exit")
    
    # Create renderer for UI
    renderer = StreamRenderer(console)

    while True:
        txt = Prompt.ask("[bold cyan]You[/bold cyan]")
        if txt.strip() in ("/exit", "/quit"):
            break
        if txt.strip() == "/reload":
            rebuild_agent()
            console.print("[reload] config reloaded")
            continue
        if txt.strip().startswith("/save"):
            history = state["agent"].history if state["agent"] else []
            with open("session.md", "a", encoding="utf-8") as f:
                f.write("\n".join(history) + "\n")
            console.print("[save] session.md updated")
            continue
        if txt.strip() == "/reset" and state["agent"]:
            state["agent"].history.clear()
            console.print("[reset] history cleared")
            continue
        if txt.strip().startswith("/mem"):
            _handle_memory(txt, state["store"], state["retr"])
            continue
        if txt.strip().startswith("/selfpatch"):
            _handle_selfpatch(txt, selfpatch)
            continue
        if txt.strip().startswith("/autopatch"):
            _handle_autopatch(txt, autopatch)
            continue
        if txt.strip().startswith("/tool "):
            _handle_tool_action(txt, state["agent"])
            continue
        if txt.strip().startswith("/template"):
            _handle_template(txt, state["agent"])
            continue
        agent: WitnessAgent = state["agent"]

        if state["dual_brain"] is not None:
            dual: DualBrain = state["dual_brain"]

            # Print "Ark:" before dual-brain output starts
            console.print("Ark: ", style="green bold", end="")

            # Start tracking generation
            renderer.start_generation()

            # Create streaming callbacks with token tracking
            stream_analysis_cb = renderer.create_stream_callback(style="green")
            stream_final_cb = renderer.create_stream_callback(style="default")
            
            res = dual.step(
                txt,
                system_instruction=state["cfg"].chat.system_prompt,
                stream_analysis=stream_analysis_cb,
                stream_final=stream_final_cb,
            )
            console.print()  # newline after streaming

            # Print all metrics using renderer
            loop_state = res.get("loop_state") or {}
            evolutions = evolution.maybe_evolve(loop_state)
            renderer.print_metrics(
                loop_info=state.get("loop_info"),
                loop_state=loop_state,
                evolutions=evolutions,
            )
            continue

        # Start tracking generation
        renderer.start_generation()
        
        # Create streaming callback with token tracking
        stream_cb = renderer.create_stream_callback(style="green bold")

        result = agent.step(
            txt,
            system_instruction=state["cfg"].chat.system_prompt,
            return_events=True,
            stream=stream_cb,
        )
        console.print()

        # Print all metrics using renderer
        loop_state = agent.last_loop_state or {}
        evolutions = evolution.maybe_evolve(loop_state)
        renderer.print_metrics(
            loop_info=state.get("loop_info"),
            loop_state=loop_state,
            evolutions=evolutions,
        )


def _handle_memory(command: str, store: MemoryStore | None, retriever: Retriever | None) -> None:
    if store is None:
        console.print("[mem] store chưa sẵn sàng.")
        return
    stripped = command.strip()
    
    # Help text
    if stripped == "/mem":
        console.print("/mem [yellow]graph | find <query> | clear[/yellow]")
        console.print("  graph - Show memory clusters")
        console.print("  find <query> - Search memories")
        console.print("  clear - Delete all memories")
        return
    
    # Clear all memories
    if stripped == "/mem clear":
        console.print("[mem] ⚠️  This will delete ALL conversation memories!")
        confirm = console.input("[mem] Type 'yes' to confirm: ")
        if confirm.strip().lower() != "yes":
            console.print("[mem] cancelled")
            return
        deleted = store.clear_all()
        console.print(f"[mem] cleared {deleted} entries")
        return
    
    # Graph
    if stripped.startswith("/mem graph"):
        if not retriever:
            console.print("[mem] retriever chưa sẵn sàng.")
            return
        clusters = retriever.graph_view()
        for idx, bucket in enumerate(clusters):
            console.print(f"[mem] cluster {idx}: {bucket[:5]}")
        return
    
    # Find
    if stripped.startswith("/mem find"):
        if not retriever:
            console.print("[mem] retriever chưa sẵn sàng.")
            return
        query = stripped[len("/mem find") :].strip()
        if not query:
            console.print("/mem find <query>")
            return
        matches = retriever.retrieve(query)
        console.print(f"[mem] matches: {matches or 'trống'}")
        return
    
    # Unknown subcommand
    console.print("[mem] unknown command, use /mem for help")


def _handle_autopatch(command: str, engine: AutoPatchEngine) -> None:
    payload = command[len("/autopatch") :].strip()
    if not payload:
        console.print("/autopatch <json | @file>")
        return
    try:
        path = engine.stage_instruction(payload)
        console.print(f"[autopatch] staged {Path(path).name}")
    except SelfPatchError as exc:
        console.print(f"[autopatch] lỗi: {exc}")


def _handle_tool_action(command: str, agent: WitnessAgent | None) -> None:
    if agent is None:
        console.print("[tool] Agent chưa sẵn sàng.")
        return
    payload = command[len("/tool") :].strip()
    if ":" not in payload:
        console.print("/tool run:\"dir\" | python:\"print(1)\" | open:\"C:/...\"")
        return
    action, data = payload.split(":", 1)
    data = data.strip().strip('"').strip("'")
    try:
        result = agent.run_tool(action.strip(), [data])
        console.print(f"[tool] code={result['returncode']} stdout={result['stdout']} stderr={result['stderr']}")
    except Exception as exc:
        console.print(f"[tool] lỗi: {exc}")


def _handle_template(command: str, agent: WitnessAgent | None) -> None:
    if agent is None:
        console.print("[template] Agent chưa sẵn sàng.")
        return
    parts = command.split(maxsplit=1)
    if len(parts) == 1:
        console.print("/template <mode> (vd: auto|llama|manual)")
        return
    agent.set_template(parts[1].strip())
    console.print(f"[template] switched to {parts[1].strip()}")


def _handle_selfpatch(command: str, manager: SelfPatchManager) -> None:
    parts = command.split()
    if len(parts) == 1:
        console.print("/selfpatch [list|dryrun|apply|revert] ...")
        return
    action = parts[1]
    try:
        if action == "list":
            entries = manager.scan_patches()
            if not entries:
                console.print("Không có patch trong thư mục.")
                return
            for item in entries:
                console.print(f"- {item['id']}")
        elif action == "dryrun" and len(parts) >= 3:
            console.print(manager.dry_run_apply(parts[2]))
        elif action == "apply" and len(parts) >= 3:
            console.print(manager.apply_patch(parts[2]))
        elif action == "revert" and len(parts) >= 3:
            console.print(manager.revert_patch(parts[2]))
        else:
            console.print("Cú pháp: /selfpatch list|dryrun <id>|apply <id>|revert <backup>")
    except SelfPatchError as exc:
        console.print(f"[selfpatch] lỗi: {exc}")


def _handle_tools(command: str, agent: WitnessAgent, runner: ToolRunner) -> None:
    if agent is None:
        console.print("[tools] Agent chưa sẵn sàng.")
        return
    parts = command.split(maxsplit=2)
    if len(parts) == 1:
        console.print("/tools [list|allow|deny|run] ...")
        return
    action = parts[1]
    if action == "list":
        allowlist = runner.list_allowlist()
        console.print(f"Allowlist: {allowlist or 'trống'}")
        return
    if action in {"allow", "deny"} and len(parts) == 3:
        pattern = parts[2].strip('"')
        if action == "allow":
            runner.allow(pattern)
            console.print(f"[tools] đã thêm {pattern}. Nhớ cập nhật config.yaml để persist.")
        else:
            runner.deny(pattern)
            console.print(f"[tools] đã gỡ {pattern}.")
        return
    if action == "run" and len(parts) == 3:
        tokens = shlex.split(parts[2])
        if not tokens:
            console.print("[tools] thiếu command.")
            return
        cmd, *args = tokens
        try:
            result = agent.run_tool(cmd, args)  # type: ignore[arg-type]
            console.print(f"[tools] code={result['returncode']} stdout={result['stdout']} stderr={result['stderr']}")
        except Exception as exc:  # pragma: no cover - interactive
            console.print(f"[tools] lỗi: {exc}")
        return
    console.print("/tools list|allow|deny|run")


def run_eval(config_path: str):
    console.print("[eval] running minimal scenarios…")
    manager = ConfigManager(config_path)
    cfg = manager.config
    scenarios_path = Path("data/eval_scenarios.yaml")
    scenarios = []
    if scenarios_path.exists():
        with scenarios_path.open("r", encoding="utf-8") as f:
            payload = yaml.safe_load(f) or {}
            scenarios = (payload.get("scenarios") or [])[:3]
    if not scenarios:
        console.print("[eval] no scenarios configured")
        console.print("[eval] done (minimal)")
        return

    tok, _, gen_fn = ForgeLoader._mock()
    base_decode = build_base_decode(cfg.model)
    store = MemoryStore(cfg.memory.db_path)
    embedder = build_embedder(
        cfg.memory.embedder,
        cfg.memory.embedding_model,
        cache_folder=cfg.loops.flame.embedder_cache_dir,
        device=None,
    )
    vector_store = None
    if cfg.memory.enabled:
        base_memories = store.recent_memories(128)
        if base_memories:
            embedder.fit(base_memories)
        dim = getattr(embedder, "dimension", len(base_memories) or 384) or 384
        vector_store = VectorStore(
            cfg.memory.db_path,
            max(32, dim),
            factory=cfg.memory.vector_factory,
            metric=cfg.memory.vector_metric,
            normalize=cfg.memory.normalize_embeddings,
        )
        store.attach_semantic_hook(embedder.embed, vector_store)
    retr = Retriever(store, embedder, vector_store, k=cfg.memory.k)
    vocab = build_vocab_from_mem(store.recent_memories(256), min_freq=2)
    loop_cfg = _loop_config(cfg)
    loops = Loops(loop_cfg, vocab)
    agent = WitnessAgent(tok, gen_fn, base_decode, loops, store, retr, template_manager=None)

    scores = []
    for item in scenarios:
        user = item.get("user", "")
        out = agent.step(user)
        scores.append(len(out))
        console.print(f"[eval] {item.get('name', 'scenario')} -> {out[:60]}...")
    console.print(f"[eval] ran {len(scores)} scenarios")
    console.print("[eval] done (minimal)")


def run_upgrade(config_path: str, trigger: str = "manual"):
    manager = ConfigManager(config_path)
    cfg = manager.config
    model_root = Path(cfg.model.path).resolve()
    patch_dir_override = None
    targeted_copy = False
    if cfg.self_upgrade.apply_to_model:
        patch_dir_override = Path(cfg.self_upgrade.patch_dir).resolve()
        targeted_copy = True
    controller = ControlledPatchManager(
        cfg.self_upgrade,
        repo_root=model_root if cfg.self_upgrade.apply_to_model else Path.cwd(),
        db_path=cfg.memory.db_path,
        patch_dir_override=patch_dir_override,
        targeted_copy=targeted_copy,
    )
    up = SelfUpgrade(
        config_path,
        patch_dir=cfg.self_upgrade.patch_dir,
        upgrade_cfg=cfg.self_upgrade,
        controller=controller,
        memory_db_path=cfg.memory.db_path,
    )
    if trigger == "manual":
        console.print("[upgrade] tạo patch config…")
        path = up.propose(
            "manual tweak",
            {"model.temperature": 0.65, "model.frequency_penalty": 0.35},
        )
        console.print(f"[upgrade] patch tại {path}. Dùng witness-forge patch-apply --path {path} để áp dụng.")
    else:
        console.print(f"[upgrade] unsupported trigger={trigger}")
