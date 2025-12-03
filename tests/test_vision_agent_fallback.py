from __future__ import annotations

from types import SimpleNamespace

from witness_forge.agents.web_agent import VisionWebAgent


class DummyResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        return None


def test_vision_agent_http_fallback(monkeypatch):
    # Force using HTTP fallback path and mock requests + bs4
    agent = VisionWebAgent(text_only_fallback=True)

    def fake_get(url, timeout=None, headers=None, allow_redirects=True):
        return DummyResponse("<html><body>Hello World</body></html>")

    def fake_bs4(html, parser):
        class _S:
            def get_text(self, sep="\n", strip=True):
                return "Hello World"

            def select(self, selector):
                return []

        return _S()

    monkeypatch.setitem(__import__("sys").modules, "requests", SimpleNamespace(get=fake_get))
    monkeypatch.setitem(__import__("sys").modules, "bs4", SimpleNamespace(BeautifulSoup=fake_bs4))

    result = agent._http_fallback("https://example.com", selector=None, err="force-fallback")

    assert result["returncode"] == 0
    assert "Hello World" in result["stdout"]
