from __future__ import annotations

from pathlib import Path

from witness_forge.tools.dispatcher import ToolDispatcher


class DummyRunner:
    def __init__(self):
        self.calls = []

    def execute(self, cmd, args):
        self.calls.append((cmd, list(args)))
        return {"stdout": "ok", "stderr": "", "returncode": 0}


def test_tool_dispatcher_python(tmp_path):
    runner = DummyRunner()
    dispatcher = ToolDispatcher(
        runner,
        allow_python=True,
        allow_powershell=False,
        allow_bat=False,
        allow_filesystem_write=True,
        max_bytes=1024,
        local_llm_entrypoint=None,
    )
    result = dispatcher.run_python("print('hello')")
    assert "hello" in result["stdout"]

    script = tmp_path / "hello.txt"
    dispatcher.write_file(f"{script}::content")
    assert script.read_text(encoding="utf-8") == "content"

    output = dispatcher.open_path(str(script))
    assert "content" in output["stdout"]
    dispatcher.run_shell("echo hi")
    assert runner.calls[-1][0] in {"cmd.exe", "bash"}
