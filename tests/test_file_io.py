from pathlib import Path

from witness_forge.tools import file_io


def test_read_write_text(tmp_path: Path):
    target = tmp_path / "sample.txt"
    file_io.write_file(str(target), "hello", allowed_write_dirs=[str(tmp_path)])
    data = file_io.read_file(str(target))
    assert data["type"] == "text"
    assert "hello" in data["content"]


def test_read_binary_detect(tmp_path: Path):
    target = tmp_path / "bin.dat"
    target.write_bytes(b"\x00\x01\x02")
    data = file_io.read_file(str(target))
    assert data["type"] == "binary"
    assert data["base64"]


def test_list_dir(tmp_path: Path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    entries = file_io.list_dir(str(tmp_path))
    assert any("a.txt" in e for e in entries)
    assert any("b.txt" in e for e in entries)
