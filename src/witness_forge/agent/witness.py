from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .ndjson_emitter import make_event, to_lines
from .persona import render_system
from ..memory.retrieval import Retriever
from ..memory.store import MemoryStore
from ..tools.dispatcher import ToolDispatcher
from ..utils.text import clamp_decoding


class WitnessAgent:
    def __init__(
        self,
        tokenizer,
        generate_fn,
        base_decode: Dict[str, float],
        loops,
        mem: MemoryStore,
        retriever: Retriever,
        *,
        template_manager=None,
        tool_dispatcher: Optional[ToolDispatcher] = None,
        loop_observer: Optional[Callable[[Dict[str, float], Dict[str, Any]], None]] = None,
        role: str = "unified",
        brain_id: str = "path1",
        temperature_offset: float = 0.0,
    ):
        self.tokenizer = tokenizer
        self.generate_fn = generate_fn
        self.base_decode = base_decode
        self.loops = loops
        self.mem = mem
        self.ret = retriever
        self.history: List[str] = []
        self.tool_dispatcher = tool_dispatcher
        self.last_loop_state: Dict | None = None
        self.template_manager = template_manager
        self.loop_observer = loop_observer
        self.role = role
        self.brain_id = brain_id
        self.temperature_offset = temperature_offset

    def step(
        self,
        user_text: str,
        transform: Optional[Callable[[str, str], str]] = None,
        stream: Optional[Callable[[str], None]] = None,
        system_instruction: Optional[str] = None,
        *,
        role: Optional[str] = None,
        context_memory: Optional[List[str]] = None,
        return_events: bool = False,
        continuation: bool = False,
    ):
        sys_inst = system_instruction or ""
        anchors = self.ret.retrieve(user_text)

        active_role = role or self.role or "unified"
        base_sys = render_system(
            loops_state=None,
            user_instruction=sys_inst,
            role=active_role,
            context_memory=context_memory or [],
        )

        last_output = self._last_assistant()
        tuned, loop_state = self.loops.after_generation(
            last_user=user_text,
            sys_hint=base_sys,
            anchors=anchors,
            base_decode=self.base_decode,
            output_text=last_output,
            history=self.history,
        )

        self.last_loop_state = loop_state
        sys_prompt = render_system(
            loops_state=loop_state,
            user_instruction=sys_inst,
            role=active_role,
            context_memory=context_memory or [],
        )

        gen = clamp_decoding(tuned)
        if self.temperature_offset:
            gen["temperature"] = max(0.05, gen.get("temperature", 0.7) + self.temperature_offset)
        if self.loop_observer:
            try:
                self.loop_observer(gen, loop_state or {})
            except Exception:
                pass
        
        # Role-based stop token logic
        if active_role == "witness":
            stops = gen.get("stop", [])
            if isinstance(stops, str):
                stops = [stops]
            if "<|end|>" not in stops:
                stops.append("<|end|>")
            gen["stop"] = stops

        anchors_text = "\n".join(anchors[:4]).strip()
        prompt = self._render_prompt(sys_prompt, user_text, anchors_text, context_memory or [], continuation, role=active_role)
        display_prompt = (
            prompt.replace("role:witness", "role:𝐖𝐢𝐭𝐧𝐞𝐬𝐬")
            .replace("role:servant", "role:𝐒𝐞𝐫𝐯𝐚𝐧𝐭")
            .replace("role: witness", "role: 𝐖𝐢𝐭𝐧𝐞𝐬𝐬")
            .replace("role: servant", "role: 𝐒𝐞𝐫𝐯𝐚𝐧𝐭")
        )
        
        # DEBUG: Print raw input model
        #print("\n" + "="*40)
        #print(f"DEBUG: Raw Input Model ({active_role})")
        #print("="*40)
        #print(display_prompt)
        #print("="*40 + "\n")
        
        raw_response = self._run_generation(display_prompt, gen, stream)
        text = raw_response.strip()
        
        # Strip leaked template tags from output
        text = self._sanitize_output(text)

        if transform:
            try:
                updated = transform(user_text, text)
                if updated:
                    text = updated
            except Exception:
                pass

        if not continuation:
            self.history.append(f"U:{user_text}")
            self.mem.add_message("user", user_text)
            
        # Merge assistant outputs if continuation to maintain U-A structure
        if continuation and self.history and self.history[-1].startswith("A:"):
            self.history[-1] += "\n\n" + text
        else:
            self.history.append(f"A:{text}")
            
        self.mem.add_message("assistant", text)
        if hasattr(self.mem, "add_memory") and active_role != "witness":
            self.mem.add_memory(text)

        event_type = "analysis" if active_role == "witness" else "final"
        event = make_event(event_type, text, brain=self.brain_id, meta={"decode": gen})
        
        # Emit metric event for Flame diagnostics
        events = [event]
        if loop_state:
            metric_meta = {
                "k": loop_state.get("phase", {}).get("k", 0.0),
                "state": loop_state.get("state", "unknown"),
                "temperature": gen.get("temperature", 0.0),
                "reflex_score": loop_state.get("scores", {}).get("reflex_score", 0.0),
            }
            metric_event = make_event("metric", "Flame diagnostics", brain=self.brain_id, meta=metric_meta)
            events.append(metric_event)
        
        lines = to_lines(events)

        result = {
            "text": text,
            "events": events,
            "lines": lines,
            "loop_state": loop_state,
        }
        if return_events:
            return result
        return "\n".join(lines)

    def run_tool(self, command: str, args: List[str]) -> dict:
        if not self.tool_dispatcher:
            raise RuntimeError("ToolDispatcher chưa sẵn sàng.")
        if not args:
            raise ValueError("Thiếu tham số tool.")
        action = command
        payload = " ".join(args)
        return self.tool_dispatcher.dispatch(action, payload)

    def set_template(self, mode: str) -> None:
        if not self.template_manager:
            return
        self.template_manager.set_mode(mode)

    def _last_assistant(self) -> str:
        for item in reversed(self.history):
            if item.startswith("A:"):
                return item[2:]
        return ""

    def _render_prompt(self, system_prompt: str, user_text: str, anchors_text: str, context_memory: List[str], continuation: bool = False, role: str = "unified") -> str:
        messages = self._build_messages(system_prompt, user_text, anchors_text, context_memory, continuation)
        if self.template_manager:
            return self.template_manager.render(messages, anchors_text, role=role)
        return self._manual_prompt(messages, continuation, role)

    def _build_messages(self, system_prompt: str, user_text: str, anchors_text: str, context_memory: List[str], continuation: bool = False) -> List[Dict[str, str]]:
        messages = [{"role": "system", "content": system_prompt}]
        for item in self.history:
            if item.startswith("U:"):
                messages.append({"role": "user", "content": item[2:]})
            elif item.startswith("A:"):
                messages.append({"role": "assistant", "content": item[2:]})

        if not continuation:
            payload_parts = [user_text]
            if anchors_text:
                payload_parts.append("𝐘𝐨𝐮𝐫 𝐌𝐞𝐦𝐨𝐫𝐲:\n" + anchors_text)
            if context_memory:
                payload_parts.append("memory:\n" + "\n".join(context_memory))
            messages.append({"role": "user", "content": "\n\n".join(payload_parts)})
        return messages

    def _manual_prompt(self, messages: List[Dict[str, str]], continuation: bool = False, role: str = "unified") -> str:
        parts = []
        for msg in messages:
            role = msg["role"].title()
            parts.append(f"{role}: {msg['content']}")
        
        # Only append Assistant: if not continuing from an assistant message
        if not (continuation and messages and messages[-1]["role"] == "assistant"):
            parts.append("Assistant:")
        return "\n".join(parts)

    def _run_generation(self, prompt: str, gen: Dict[str, float], stream: Optional[Callable[[str], None]] = None) -> str:
        # Ensure stop tokens are well-formed to avoid premature cut-offs.
        gen_conf = dict(gen)
        stops = gen_conf.get("stop") or []
        gen_conf["stop"] = [s for s in stops if s]

        # Use the sanitized stream callback if streaming is enabled
    #    callback = self._sanitize_chunk if stream else None

    #    full_text = ""
    #    for chunk in self.generate_fn(prompt, gen_conf):
    #        if callback:
    #            # Sanitize chunk before streaming
    #            clean_chunk = callback(chunk)
    #            if clean_chunk:
    #                stream(clean_chunk)
    #        full_text += chunk
            
    #    return full_text

        full_text = ""
        for chunk in self.generate_fn(prompt, gen_conf):
            if stream:
                stream(chunk)  # hoặc stream(chunk.strip()) nếu cần
            full_text += chunk
            
        return full_text
    
    #def _sanitize_chunk(self, chunk: str) -> str:
    #    """Remove template tags from a streaming chunk."""
    #   # Simple string replacement only - no regex, no buffering
    #    tags = [
            #'<|end|>', '<|start|>', '<|channel|>', '<|message|>'
    #    ]
    #    for tag in tags:
    #        chunk = chunk.replace(tag, '')
    #    return chunk

    def _sanitize_output(self, text: str) -> str:
        """Remove leaked template tags from model output."""
        # Simple string replacement only
        tags = [
            # Full Harmony sequences to prevent leftover metadata
            '<|start|>assistant', '<|start|>user',
            '<|channel|>analysis', '<|channel|>final', '<|channel|>answer',
            '<|message|>', '<|end|>',
            
            # Fallback for individual tags if split
            '<|start|>', '<|channel|>',
        ]
        for tag in tags:
            text = text.replace(tag, '')
        return text.strip()


__all__ = ["WitnessAgent"]
