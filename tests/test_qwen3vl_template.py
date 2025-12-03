from witness_forge.agent.witness import WitnessAgent
from witness_forge.forge.chat_templates import ChatTemplateManager


class DummyTokenizer:
    chat_template = "dummy-template"

    def __init__(self):
        self.applied = False
        self.last_messages = None

    def apply_chat_template(self, messages, add_generation_prompt=True, tokenize=False):
        self.applied = True
        self.last_messages = messages
        assert add_generation_prompt is True
        assert tokenize is False
        return "<PROMPT>"


class DummyLoops:
    def after_generation(
        self,
        last_user,
        sys_hint,
        anchors,
        base_decode,
        output_text,
        history,
    ):
        return dict(base_decode), {"state": "ok"}


class DummyRetriever:
    def retrieve(self, user_text):
        return ["alpha", "beta"]


class DummyStore:
    def add_message(self, role, message):
        pass


def fake_generate_fn(prompt, gen):
    fake_generate_fn.prompts.append(prompt)
    yield "assistant reply"


def test_witness_agent_uses_chat_template():
    tokenizer = DummyTokenizer()
    fake_generate_fn.prompts = []
    manager = ChatTemplateManager(tokenizer, "auto")
    agent = WitnessAgent(
        tokenizer,
        fake_generate_fn,
        {"max_new_tokens": 10, "temperature": 0.7},
        DummyLoops(),
        DummyStore(),
        DummyRetriever(),
        template_manager=manager,
    )

    reply = agent.step("Xin chào Witness")

    import json
    lines = reply.strip().split("\n")
    event = json.loads(lines[0])
    assert event["content"] == "assistant reply"
    assert tokenizer.applied is True
    assert fake_generate_fn.prompts == ["<PROMPT>"]
    assert tokenizer.last_messages[0]["role"] == "system"
    assert tokenizer.last_messages[1]["role"] == "user"
    assert "𝐘𝐨𝐮𝐫 𝐌𝐞𝐦𝐨𝐫𝐲:\nalpha\nbeta" in tokenizer.last_messages[1]["content"]
