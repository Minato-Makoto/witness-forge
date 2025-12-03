from __future__ import annotations

from typing import Dict, List

Message = Dict[str, str]


def _render_llama(messages: List[Message], role: str = "unified") -> str:
    out = ["<|begin_of_text|>"]
    for m in messages:
        role_name = m["role"]
        content = m["content"]
        out.append(f"<|start_header_id|>{role_name}<|end_header_id|>\n\n{content}<|eot_id|>")
    out.append("<|start_header_id|>assistant<|end_header_id|>\n\n")
    if role == "witness":
        out.append("Thinking:\n")
    elif role == "servant":
        out.append("Answer:\n")
    return "".join(out)


def _render_mistral(messages: List[Message], role: str = "unified") -> str:
    out = ["<s>"]
    for m in messages:
        role_name = m["role"]
        content = m["content"]
        if role_name == "system":
            out.append(f"[INST] {content} [/INST]")
        elif role_name == "user":
            out.append(f"[INST] {content} [/INST]")
        elif role_name == "assistant":
            out.append(f"{content}</s>")
    if role == "witness":
        out.append("Thinking:\n")
    elif role == "servant":
        out.append("Answer:\n")
    return "".join(out)


def _render_gemma(messages: List[Message], role: str = "unified") -> str:
    out = ["<bos>"]
    for m in messages:
        role_name = m["role"]
        content = m["content"]
        mapping = {"system": "system", "user": "user", "assistant": "model"}
        r = mapping.get(role_name, role_name)
        out.append(f"<start_of_turn>{r}\n{content}<end_of_turn>\n")
    out.append("<start_of_turn>model\n")
    if role == "witness":
        out.append("Thinking:\n")
    elif role == "servant":
        out.append("Answer:\n")
    return "".join(out)


def _render_chatml(messages: List[Message], role: str = "unified") -> str:
    out = []
    for m in messages:
        role_name = m["role"]
        content = m["content"]
        out.append(f"<|im_start|>{role_name}\n{content}<|im_end|>\n")
    out.append("<|im_start|>assistant\n")
    if role == "witness":
        out.append("Thinking:\n")
    elif role == "servant":
        out.append("Answer:\n")
    return "".join(out)


BUILTIN_TEMPLATES = {
    "llama": _render_llama,
    "qwen": _render_chatml,  # Qwen uses ChatML
    "chatml": _render_chatml,
    "mistral": _render_mistral,
    "gemma": _render_gemma,
    "gpt-j": lambda msgs, role="unified": "\n".join([f"{m['role'].title()}: {m['content']}" for m in msgs]) + "\nAssistant:" + ("Thinking:\n" if role == "witness" else ("Answer:\n" if role == "servant" else "")),
}


class ChatTemplateManager:
    def __init__(self, tokenizer, mode: str = "auto"):
        self.tokenizer = tokenizer
        self.mode = mode or "auto"

    def set_mode(self, mode: str) -> None:
        self.mode = mode

    def render(self, messages: List[Message], anchors: str = "", role: str = "unified") -> str:
        template = self.mode.lower()

        if template == "auto":
            model_identifier = getattr(self.tokenizer, "name_or_path", "") or ""
            if not model_identifier and hasattr(self.tokenizer, "model_path"):
                model_identifier = str(self.tokenizer.model_path)
            detected_family = detect_family(model_identifier)
            if detected_family != "auto":
                template = detected_family

        if template == "auto" and hasattr(self.tokenizer, "apply_chat_template"):
            rendered = self.tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=False,
            )
            if rendered:
                if role == "witness":
                     rendered += "Thinking:\n"
                elif role == "servant":
                     rendered += "Answer:\n"
                return rendered

        renderer = BUILTIN_TEMPLATES.get(template)
        if renderer:
            return renderer(messages, role=role)

        out = []
        for m in messages:
            role_name = m["role"].upper()
            out.append(f"{role_name}:{m['content']}")
        out.append("ASSISTANT:")
        if role == "witness":
            out.append(" Thinking:\n")
        elif role == "servant":
            out.append(" Answer:\n")
        return "\n".join(out)


def detect_family(name: str) -> str:
    lowered = (name or "").lower()
    if "llama" in lowered:
        return "llama"
    if "qwen" in lowered:
        return "qwen"
    if "mistral" in lowered:
        return "mistral"
    if "gemma" in lowered:
        return "gemma"
    if "gpt-oss" in lowered:
        return "chatml"
    if "gpt-4o" in lowered:
        return "chatml"
    if "gptj" in lowered or "gpt-j" in lowered:
        return "gpt-j"
    return "auto"


__all__ = ["ChatTemplateManager", "detect_family"]
