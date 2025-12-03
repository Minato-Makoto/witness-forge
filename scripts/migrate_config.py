#!/usr/bin/env python
"""
Chuyển config cũ sang schema mới (adapter/quant/selfpatch/tools).
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path

import yaml


DEFAULT_ADAPTER = {"enabled": False, "type": "lora", "path": "", "load_mode": "merge"}
DEFAULT_QUANT = {
    "dtype": "auto",
    "load_8bit": False,
    "load_4bit": False,
    "device_map": "auto",
    "offload_folder": None,
}
DEFAULT_SELFPATCH = {
    "enabled": False,
    "patches_dir": "./patches",
    "require_confirmation": True,
    "validator_cmd": None,
    "run_validators": True,
}
DEFAULT_TOOLS = {"allowlist": [], "require_confirm": True}

def migrate(path: Path) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    model = data.setdefault("model", {})
    quant = model.get("quant")
    if not quant:
        quant = copy.deepcopy(DEFAULT_QUANT)
        for key in ("dtype", "device_map", "load_8bit", "load_4bit"):
            if key in model:
                quant[key if key != "device_map" else "device_map"] = model.pop(key)
        model["quant"] = quant
    model.setdefault("adapter", copy.deepcopy(DEFAULT_ADAPTER))
    data.setdefault("selfpatch", copy.deepcopy(DEFAULT_SELFPATCH))
    data.setdefault("tools", copy.deepcopy(DEFAULT_TOOLS))
    if "self_upgrade" in data:
        data["self_upgrade"].setdefault("require_confirmation", True)
        data["self_upgrade"].setdefault("validator_cmd", None)
        data["self_upgrade"].setdefault("run_validators", True)

    backup = path.with_suffix(".bak")
    backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"Đã migrate {path} (backup tại {backup}).")


def main():
    parser = argparse.ArgumentParser(description="Migrate config.yaml sang schema mới.")
    parser.add_argument("config", nargs="?", default="config.yaml")
    args = parser.parse_args()
    migrate(Path(args.config))


if __name__ == "__main__":
    main()
