import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path.cwd() / "src"))

from witness_forge.config import ConfigManager
from witness_forge.forge.loader import ForgeLoader

def test_fixed_loader():
    print("Testing the fixed loader...")
    
    manager = ConfigManager("config.yaml")
    cfg = manager.config
    
    print(f"Loading model: {cfg.model.name}")
    tok, mdl, gen_fn = ForgeLoader.load_model(cfg.model, witness_cfg=cfg)
    
    prompt = "<|im_start|>system\nYou are helpful.<|im_end|>\n<|im_start|>user\nHi<|im_end|>\n<|im_start|>assistant\n"
    
    print("\nGenerating response...")
    chunks = []
    for chunk in gen_fn(prompt, {"max_new_tokens": 50, "temperature": 0.7}):
        chunks.append(chunk)
        print(chunk, end="", flush=True)
    
    print(f"\n\nDone! Total chunks yielded: {len(chunks)}")
    print(f"Total characters: {sum(len(c) for c in chunks)}")
    
    if len(chunks) > 200:
        print("WARNING: Generated suspiciously many chunks. Loop might not be breaking!")
    else:
        print("SUCCESS: Generation stopped appropriately.")

if __name__ == "__main__":
    test_fixed_loader()
