from rich.console import Console
from rich.style import Style
from rich.highlighter import ReprHighlighter, RegexHighlighter

console = Console()

chunks = ["Hmm, ", "let me ", "think ", "about ", "\"yo\".\n", "Count is ", "123", ".\n"]

print("--- Default Highlight=True ---")
for chunk in chunks:
    console.print(chunk, end="", style=Style(color=None), highlight=True)
print("\n")

print("--- ReprHighlighter ---")
highlighter = ReprHighlighter()
for chunk in chunks:
    console.print(highlighter(chunk), end="", style=Style(color=None))
print("\n")

print("--- Buffered Line Test ---")
buffer = ""
for chunk in chunks:
    buffer += chunk
    if "\n" in buffer:
        line, buffer = buffer.split("\n", 1)
        console.print(line, style=Style(color=None), highlight=True)
if buffer:
    console.print(buffer, style=Style(color=None), highlight=True)
print("\n")
