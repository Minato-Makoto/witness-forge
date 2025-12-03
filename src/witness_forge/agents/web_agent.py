from __future__ import annotations

import base64
import ipaddress
import json
import random
import string
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse


class VisionWebAgent:
    """
    Playwright-backed web agent with SoM overlay and text-only fallback.
    Payload formats:
      - visit::URL
      - action::(click|type|scroll)::URL::TARGET_ID[::TEXT]
    Returns stdout text (cleaned body + som map + screenshot path).
    """

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout_ms: int = 15000,
        screenshot_dir: str = "./data/screens",
        window_size: Tuple[int, int] = (1280, 720),
        text_only_fallback: bool = True,
        enable_screenshots: bool = False,
    ):
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.screenshot_dir = Path(screenshot_dir)
        self.window_size = window_size
        self.text_only_fallback = text_only_fallback
        self.enable_screenshots = enable_screenshots
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def execute(self, payload: str) -> Dict[str, str | int]:
        parts = [p for p in payload.split("::") if p]
        if not parts:
            return {"stdout": "", "stderr": "Missing payload", "returncode": 1}

        if parts[0] == "visit" and len(parts) >= 2:
            return self._visit(parts[1])
        if parts[0] == "action" and len(parts) >= 3:
            return self._act(parts[1], parts[2], parts[3] if len(parts) >= 4 else None, parts[4] if len(parts) >= 5 else None)
        # Fallback: treat payload as URL to visit
        if len(parts) == 1:
            return self._visit(parts[0])
        return {"stdout": "", "stderr": f"Unsupported payload: {payload}", "returncode": 1}

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _visit(self, url: str) -> Dict[str, str | int]:
        if not self._is_safe_url(url):
            return {"stdout": "", "stderr": f"URL not allowed: {url}", "returncode": 1}

        # Try Playwright; fallback to requests if missing.
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover - import guard
            if self.text_only_fallback:
                return self._http_fallback(url, selector=None, err=f"Playwright unavailable: {exc}")
            return {"stdout": "", "stderr": f"Playwright unavailable: {exc}", "returncode": 1}

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless, timeout=self.timeout_ms)
                context = browser.new_context(
                    viewport={"width": self.window_size[0], "height": self.window_size[1]},
                )
                page = context.new_page()
                page.goto(url, timeout=self.timeout_ms, wait_until="domcontentloaded")

                som = self._inject_som(page)
                body_text = page.inner_text("body", timeout=self.timeout_ms)
                screenshot_path = self._save_screenshot(page) if self.enable_screenshots else None

                # Keep browser open briefly if not headless (for visual debugging)
                if not self.headless:
                    import time
                    print(f"[VisionWebAgent] Browser window visible. Keeping open for 5 seconds...")
                    time.sleep(5)
                
                context.close()
                browser.close()

                payload = {
                    "title": page.title(),
                    "text": body_text[:6000],
                    "som": som,
                    "screenshot": screenshot_path,
                }
                return {"stdout": json.dumps(payload), "stderr": "", "returncode": 0}
        except Exception as exc:  # pragma: no cover - runtime errors
            if self.text_only_fallback:
                return self._http_fallback(url, selector=None, err=str(exc))
            return {"stdout": "", "stderr": str(exc), "returncode": 1}

    def _act(self, action: str, url: str, target_id: Optional[str], text: Optional[str]) -> Dict[str, str | int]:
        if not self._is_safe_url(url):
            return {"stdout": "", "stderr": f"URL not allowed: {url}", "returncode": 1}

        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover - import guard
            return {"stdout": "", "stderr": f"Playwright unavailable: {exc}", "returncode": 1}

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless, timeout=self.timeout_ms)
                context = browser.new_context(
                    viewport={"width": self.window_size[0], "height": self.window_size[1]},
                )
                page = context.new_page()
                page.goto(url, timeout=self.timeout_ms, wait_until="domcontentloaded")
                som = self._inject_som(page)

                selector = ""
                if target_id:
                    selector = f"[data-som-id='{target_id}']"
                if action == "click" and selector:
                    page.click(selector, timeout=self.timeout_ms)
                elif action == "type" and selector:
                    page.fill(selector, text or "", timeout=self.timeout_ms)
                elif action == "scroll":
                    page.mouse.wheel(0, 800)

                som = self._inject_som(page)
                screenshot_path = self._save_screenshot(page) if self.enable_screenshots else None
                body_text = page.inner_text("body", timeout=self.timeout_ms)
                context.close()
                browser.close()

                payload = {
                    "text": body_text[:6000],
                    "som": som,
                    "screenshot": screenshot_path,
                    "action": action,
                    "target": target_id or "",
                }
                return {"stdout": json.dumps(payload), "stderr": "", "returncode": 0}
        except Exception as exc:  # pragma: no cover - runtime errors
            return {"stdout": "", "stderr": str(exc), "returncode": 1}

    def _http_fallback(self, url: str, selector: Optional[str], err: str) -> Dict[str, str | int]:
        try:
            import requests
            from bs4 import BeautifulSoup
        except Exception as exc:  # pragma: no cover
            return {"stdout": "", "stderr": f"{err}; fallback unavailable: {exc}", "returncode": 1}

        try:
            resp = requests.get(url, timeout=self.timeout_ms / 1000.0, headers={"User-Agent": "WitnessForge/0.3"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            if selector:
                elements = soup.select(selector)
                text = "\n".join(el.get_text(strip=True) for el in elements[:5])
            else:
                text = soup.get_text("\n", strip=True)
            payload = {"text": text[:6000], "som": [], "screenshot": None, "note": f"fallback:{err}"}
            return {"stdout": json.dumps(payload), "stderr": "", "returncode": 0}
        except Exception as exc:
            return {"stdout": "", "stderr": f"{err}; fallback failed: {exc}", "returncode": 1}

    def _inject_som(self, page):
        js = """
        (() => {
          const tags = ['button','a','input','textarea','select','option'];
          const elems = Array.from(document.querySelectorAll(tags.join(',')));
          const result = [];
          elems.forEach((el, idx) => {
            const rect = el.getBoundingClientRect();
            const id = `S${idx+1}`;
            el.setAttribute('data-som-id', id);
            const mark = document.createElement('div');
            mark.style.position = 'absolute';
            mark.style.left = `${rect.left + window.scrollX}px`;
            mark.style.top = `${rect.top + window.scrollY}px`;
            mark.style.width = `${rect.width}px`;
            mark.style.height = `${rect.height}px`;
            mark.style.border = '2px solid red';
            mark.style.background = 'rgba(255,0,0,0.08)';
            mark.style.zIndex = 2147483647;
            mark.style.pointerEvents = 'none';
            mark.innerText = id;
            mark.style.color = 'red';
            mark.style.fontSize = '12px';
            mark.style.fontWeight = 'bold';
            document.body.appendChild(mark);
            result.push({
              id,
              tag: el.tagName,
              text: (el.innerText || el.value || '').slice(0,120),
              bbox: {x: rect.x, y: rect.y, w: rect.width, h: rect.height}
            });
          });
          return result;
        })();
        """
        return page.evaluate(js)

    def _save_screenshot(self, page) -> Optional[str]:
        try:
            name = "screen_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8)) + ".png"
            path = str(self.screenshot_dir / name)
            shot = page.screenshot(full_page=True)
            Path(path).write_bytes(shot)
            return path
        except Exception:
            return None

    @staticmethod
    def _is_safe_url(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        host = (parsed.hostname or "").strip()
        if not host:
            return False

        blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
        if host.lower() in blocked_hosts:
            return False

        try:
            ip_obj = ipaddress.ip_address(host)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved or ip_obj.is_link_local:
                return False
        except ValueError:
            if host.startswith("192.168.") or host.startswith("10.") or host.startswith("172.16."):
                return False
        return True


__all__ = ["VisionWebAgent"]
