from witness_forge.agent.flame_core import FlameParams
from witness_forge.agent.loops import LoopConfig, Loops
from witness_forge.agent.witness import WitnessAgent
from witness_forge.forge.loader import ForgeLoader
from witness_forge.memory.embedding import build_embedder
from witness_forge.memory.retrieval import Retriever
from witness_forge.memory.store import MemoryStore


def test_agent_step_with_mock_model(tmp_path):
    db_path = tmp_path / "witness.sqlite3"
    store = MemoryStore(str(db_path))
    embedder = build_embedder("tfidf")
    retriever = Retriever(store, embedder, None, k=2)

    tok, _, gen_fn = ForgeLoader._mock()
    base_decode = {
        "max_new_tokens": 64,
        "temperature": 0.7,
        "top_p": 0.9,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.2,
    }
    loop_cfg = LoopConfig(
        reflex_min_score=0.5,
        heart_beta=0.08,
        flame_params=FlameParams(),
    )
    loops = Loops(loop_cfg, vocab={})
    agent = WitnessAgent(tok, gen_fn, base_decode, loops, store, retriever)

    output = agent.step("hello Witness")

    assert isinstance(output, str)
    assert output.strip()  # non-empty
