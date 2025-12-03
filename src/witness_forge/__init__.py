"""Witness Forge - Local LLM agent harness."""
import sys


class _FilteredStderr:
    """Filter stderr để ẩn các warning không mong muốn"""
    
    def __init__(self, original_stderr, filters):
        self.original_stderr = original_stderr
        self.filters = filters
        
    def write(self, text):
        if not any(f in text for f in self.filters):
            self.original_stderr.write(text)
    
    def flush(self):
        self.original_stderr.flush()
    
    def fileno(self):
        return self.original_stderr.fileno()


# Setup filtered stderr trước khi import dependencies
sys.stderr = _FilteredStderr(sys.stderr, ["CUDA extension not installed"])

__all__ = ["__version__"]

__version__ = "0.1.0"
