import io

from rich.console import Console

from witness_forge.ui.renderer import StreamRenderer


def test_renderer_strips_tags_and_transitions():
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, color_system=None)
    renderer = StreamRenderer(console)

    # Simulate thinking -> final answer via NDJSON events
    renderer.stream('{"type": "analysis", "content": "Thinking phase..."}')
    renderer.stream('{"type": "final", "content": "Answer start "}')
    renderer.stream('{"type": "final", "content": "more answer"}')
    renderer.end()

    out = buf.getvalue()
    # No raw JSON leaked (ideally, but here we check content)
    assert "Thinking phase" in out
    assert "Answer start" in out
    assert "more answer" in out
    # Check styles are applied (Rich console output contains ANSI codes or text depending on setup)
    # Since force_terminal=False and color_system=None, it should be plain text.
    
    # Ensure no JSON structure leaked
    assert '{"type"' not in out
