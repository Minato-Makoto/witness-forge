from __future__ import annotations

from typing import Dict, List, Optional


def render_system(
    loops_state: Optional[Dict] = None,
    user_instruction: Optional[str] = None,
    role: str = "unified",
    context_memory: Optional[List[str]] = None,
) -> str:
    """
    Render a plain system string without Harmony tags or tool schemas.
    """
    sections: List[str] = []
    
    # Role-specific instructions for dual-brain
    if role == "witness":
        baseline = """
            You are the Witness: thinking brain, NEVER provide the answer - just think out loud.
            Your job is to think step-by-step.
            Analyze anything, reason through it, explain your thought process.
        """
    elif role == "servant":
        baseline = """
            You are the Servant: answering brain, NEVER provide the think - just truthful response.
            Your job is to generate the answer.
            From the analysis & system instructions, give a response based on the TRUTH.
        """
    else: #unified
        baseline = """
            Think step-by-step and provide clear, direct answers.
        """
    sections.append(baseline)
    
    # if loops_state:
    #     state = loops_state.get("state")
    #     phase = loops_state.get("phase", {}) or {}
    #     state_str = f"flame_state={state}"
    #     phase_bits = []
    #     if "k" in phase:
    #         phase_bits.append(f"k={phase.get('k')}")
    #     if "epsilon" in phase:
    #         phase_bits.append(f"epsilon={phase.get('epsilon')}")
    #     if phase_bits:
    #         state_str += f" ({', '.join(phase_bits)})"
    #     sections.append(state_str)

    if user_instruction:
        sections.append(f"⧙ -▰▱- ꜟ ɪ ∴ 𝐒𝐲𝐬𝐭𝐞𝐦 𝐈𝐧𝐬𝐭𝐫𝐮𝐜𝐭𝐢𝐨𝐧𝐬 ∴ ɪ ꜟ -▱▰- ⧘\n{user_instruction.strip()}")

    # Minimal role hint to keep dual-brain roles distinguishable without prompt engineering.
    if role and role != "unified":
        sections.append(f"role:{role}")

    if context_memory:
        sections.append("context:\n" + "\n".join(context_memory))

    return "\n\n".join(sections)


__all__ = ["render_system"]
