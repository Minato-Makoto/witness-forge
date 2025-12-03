import sys
from pathlib import Path

import pytest

from witness_forge.config import ToolSandboxConfig, ToolsConfig
from witness_forge.tools.runner import ToolRunner


def _cfg():
    return ToolsConfig(
        allow_exec=True,
        whitelist=[Path(sys.executable).name, sys.executable],
        require_confirm=False,
        sandbox=ToolSandboxConfig(max_runtime_seconds=5, max_stdout_bytes=2048),
    )


def test_toolrunner_dry_run(tmp_path):
    runner = ToolRunner(_cfg(), confirm_callback=None, db_path=str(tmp_path / "audit.sqlite3"))
    result = runner.run_tool(f"{sys.executable} -V", dry_run=True)
    assert result["status"] == "dry-run"


def test_toolrunner_executes_and_logs(tmp_path):
    runner = ToolRunner(_cfg(), confirm_callback=None, db_path=str(tmp_path / "audit.sqlite3"))
    result = runner.run_tool(f"{sys.executable} -c \"print('ok')\"", dry_run=False)
    assert result["returncode"] == 0
    assert "ok" in result["stdout"]
    # sqlite log exists
    assert (tmp_path / "audit.sqlite3").exists()


def test_toolrunner_denies_unlisted(tmp_path):
    cfg = ToolsConfig(allow_exec=True, whitelist=["python"], require_confirm=False)
    runner = ToolRunner(cfg, confirm_callback=None, db_path=str(tmp_path / "audit.sqlite3"))
    with pytest.raises(PermissionError):
        runner.run_tool("bash -c echo hi", dry_run=False)
