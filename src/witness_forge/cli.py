from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

import typer
import yaml
from rich.console import Console
from rich.prompt import Prompt

from .agent.self_patch_manager import ControlledPatchManager
from .config import ConfigManager
from .main import run_chat, run_eval, run_upgrade
from .tools.runner import ToolRunner as SafeToolRunner

app = typer.Typer(help="Witness Forge CLI")
console = Console()


def _load_config(config_path: str):
    manager = ConfigManager(config_path)
    return manager.config


def _build_patch_mgr(config_path: str):
    cfg = _load_config(config_path)
    
    model_root = Path(cfg.model.path).resolve()
    if model_root.is_file():
        model_root = model_root.parent
        
    patch_dir_override = None
    targeted_copy = False
    repo_root = Path.cwd()
    
    if cfg.self_upgrade.apply_to_model:
        # Only redirect runtime patches (selfpatch), NOT config patches (self_upgrade).
        # Config patches must remain global.
        # patch_dir_override = Path(cfg.self_upgrade.patch_dir).resolve() <--- REMOVED
        targeted_copy = True
        repo_root = model_root

    controller = ControlledPatchManager(
        cfg.self_upgrade,
        repo_root=repo_root,
        db_path=cfg.memory.db_path,
        patch_dir_override=patch_dir_override,
        targeted_copy=targeted_copy,
    )
    return cfg, controller


def _parse_sets(values: List[str]) -> dict:
    deltas = {}
    for item in values:
        if "=" not in item:
            raise typer.BadParameter(f"Thiếu dấu '=' trong {item}")
        key, value = item.split("=", 1)
        deltas[key.strip()] = value.strip()
    return deltas


@app.command()
def chat(
    config: str = "config.yaml",
    model_name: str = "",
    allow_selfpatch: bool = typer.Option(
        True,
        "--allow-selfpatch",
        help="Cho phép Witness tự áp dụng SelfPatch sau khi đã xác nhận và set env WITNESS_FORGE_ALLOW_SELF_PATCH.",
    ),
    use_template: Optional[bool] = typer.Option(
        None,
        "--use-template/--no-use-template",
        help="Force enable/disable chat template application when supported.",
    ),
):
    console.print("[bold red]Witness Forge[/bold red] online -- syncing with config.yaml")
    run_chat(
        config_path=config,
        model_name=model_name,
        use_template=use_template,
        allow_selfpatch=allow_selfpatch,
    )


@app.command()
def eval(config: str = "config.yaml"):
    run_eval(config)


@app.command()
def upgrade(config: str = "config.yaml", trigger: str = "manual"):
    run_upgrade(config, trigger)


@app.command("patch-generate")
def patch_generate(
    config: str = typer.Option("config.yaml", "--config"),
    describe: str = typer.Option(..., "--describe", help="Mô tả thay đổi."),
    set_value: List[str] = typer.Option([], "--set", help="key=value để chỉnh config."),
    file: Optional[str] = typer.Option(None, "--file", help="Đường dẫn file muốn đóng gói."),
    content_path: Optional[str] = typer.Option(
        None,
        "--content-path",
        help="File chứa nội dung mới (nếu bỏ trống sẽ dùng nội dung hiện tại).",
    ),
    demo_readme: bool = typer.Option(
        False,
        "--demo-readme",
        help="Tạo patch mô phỏng lên README để thử quy trình.",
    ),
):
    cfg, manager = _build_patch_mgr(config)
    if demo_readme:
        path = manager.generate_demo_patch(describe)
        console.print(f"Đã tạo patch demo: {path}")
        return
    if bool(set_value) and file:
        raise typer.BadParameter("Không thể dùng đồng thời --set và --file.")
    if set_value:
        deltas = _parse_sets(set_value)
        path = manager.generate_config_patch(config, deltas, describe, author="cli")
        console.print(f"Đã tạo patch config: {path}")
        return
    if file:
        target = Path(file)
        if content_path:
            new_content = Path(content_path).read_text(encoding="utf-8")
        else:
            new_content = target.read_text(encoding="utf-8")
        path = manager.generate_file_patch(target, new_content, describe, author="cli")
        console.print(f"Đã tạo patch file: {path}")
        return
    raise typer.BadParameter("Cần cung cấp --set, --file hoặc --demo-readme.")


@app.command("patch-apply")
def patch_apply(
    config: str = typer.Option("config.yaml", "--config"),
    path: str = typer.Option(..., "--path"),
    force: bool = typer.Option(False, "--force", help="Bỏ qua yêu cầu confirm (cần mật khẩu master)."),
):
    cfg, manager = _build_patch_mgr(config)
    preview = manager.preview(path)
    console.print(f"Patch {preview.path.name} ({preview.size_kb:.1f}KB)\nSHA: {preview.sha256}")
    console.print(preview.diff)
    dry_result = manager.apply_patch(path, dry_run=True)
    console.print(f"Dry-run tests: {dry_result['tests']['status']}")
    if dry_result["tests"]["status"] != "passed" and not force:
        raise typer.BadParameter("Tests không pass, không thể áp dụng patch.")
    token = None
    if force:
        master = os.getenv("WITNESS_FORGE_MASTER_PASS", "")
        if not master:
            raise typer.BadParameter("Thiếu env WITNESS_FORGE_MASTER_PASS cho chế độ force.")
        provided = typer.prompt("Nhập master password để force apply")
        if provided != master:
            raise typer.BadParameter("Master password sai.")
    else:
        expected = f"APPLY PATCH {preview.sha256}"
        token = typer.prompt(f"Nhập '{expected}' để xác nhận")
        if token.strip() != expected:
            raise typer.BadParameter("Chuỗi xác nhận không đúng.")
    result = manager.apply_patch(
        path,
        dry_run=False,
        approval_token=token,
        force=force,
        applied_by="cli",
    )
    console.print(f"Kết quả: {result['status']} (sha={result.get('sha256','')})")


@app.command("adapter-install")
def adapter_install(
    config: str = typer.Option("config.yaml", "--config"),
    path: str = typer.Option(..., "--path"),
    enable: bool = typer.Option(True, "--enable/--disable", help="Bật adapter ngay sau khi ghi config."),
):
    cfg_path = Path(config)
    adapter_path = Path(path).expanduser().resolve()
    if not adapter_path.exists():
        raise typer.BadParameter(f"Adapter path {adapter_path} không tồn tại.")
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    adapter_block = data.setdefault("adapter", {})
    adapter_block["path"] = str(adapter_path)
    adapter_block["enabled"] = bool(enable)
    cfg_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    console.print(f"Đã cập nhật config adapter -> {adapter_path} (enabled={enable})")


@app.command("tool-run")
def tool_run(
    config: str = typer.Option("config.yaml", "--config"),
    cmd: str = typer.Option(..., "--cmd", help='Ví dụ: "python -c \\"print(1)\\""'),
    auto: bool = typer.Option(False, "--auto-apply", help="Chạy ngay, bỏ qua confirm."),
):
    cfg = _load_config(config)
    tool_cfg = cfg.tools.model_copy(update={"require_confirm": False})
    runner = SafeToolRunner(tool_cfg, confirm_callback=None, db_path=cfg.memory.db_path)
    dry = runner.run_tool(cmd, dry_run=True)
    console.print(f"Dry-run: {dry}")
    if not auto and not typer.confirm("Thực thi command này?"):
        return
    result = runner.run_tool(cmd, dry_run=False)
    console.print(f"Return={result['returncode']}\nSTDOUT:\n{result['stdout']}\nSTDERR:\n{result['stderr']}")


def main():
    app()


if __name__ == "__main__":
    main()
