import json
import hashlib
import hmac
from pathlib import Path

import pytest

from witness_forge.agent.self_patch_manager import ControlledPatchManager
from witness_forge.config import SelfUpgradeConfig


def _make_manager(tmp_path, repo_root):
    cfg = SelfUpgradeConfig(
        patch_dir=str(tmp_path / "patches"),
        dry_run_tests=[],
        signature_key_path=str(tmp_path / "keys" / "pub.key"),
        require_approval=True,
    )
    (tmp_path / "keys").mkdir(exist_ok=True)
    return ControlledPatchManager(cfg, repo_root=repo_root, db_path=str(tmp_path / "audit.sqlite3"))


def test_patch_apply_requires_confirmation(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "README.md"
    target.write_text("hello\n", encoding="utf-8")
    manager = _make_manager(tmp_path, repo)
    patch_path = manager.generate_file_patch(target, "hello world\n", "demo", author="test")
    dry = manager.apply_patch(patch_path, dry_run=True)
    assert dry["status"] == "dry-run"
    with pytest.raises(PermissionError):
        manager.apply_patch(patch_path, dry_run=False)


def test_patch_apply_success(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg_file = repo / "config.yaml"
    cfg_file.write_text("value: 1\n", encoding="utf-8")
    manager = _make_manager(tmp_path, repo)
    patch_path = manager.generate_file_patch(cfg_file, "value: 2\n", "bump", author="test")
    dry = manager.apply_patch(patch_path, dry_run=True)
    token = f"APPLY PATCH {dry['sha256']}"
    result = manager.apply_patch(patch_path, dry_run=False, approval_token=token)
    assert result["status"] == "applied"
    assert "2" in cfg_file.read_text(encoding="utf-8")


def test_signature_verification(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg_file = repo / "cfg.txt"
    cfg_file.write_text("x\n", encoding="utf-8")
    manager = _make_manager(tmp_path, repo)
    patch_path = manager.generate_file_patch(cfg_file, "y\n", "sign", author="cli")
    payload = json.loads(Path(patch_path).read_text(encoding="utf-8"))
    sha = payload["meta"]["patch_sha256"]
    key_path = Path(manager.cfg.signature_key_path)
    key_path.write_bytes(b"secret")
    payload["signature"] = hmac.new(b"secret", sha.encode("utf-8"), hashlib.sha256).hexdigest()
    Path(patch_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    dry = manager.apply_patch(patch_path, dry_run=True)
    token = f"APPLY PATCH {dry['sha256']}"
    result = manager.apply_patch(patch_path, dry_run=False, approval_token=token)
    assert result["status"] == "applied"
