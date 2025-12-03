import sys
import os
from gguf import GGUFReader

# Model path
MODEL_PATH = r"M:\Flame-System\witness-forge\models\gpt-oss-20b-uncensored-bf16-Q2_K-GGUF\gpt-oss-20b-uncensored-bf16-q2_k.gguf"

def inspect_gguf():
    print(f"Inspecting: {MODEL_PATH}")
    if not os.path.exists(MODEL_PATH):
        print("Model file not found!")
        return

    try:
        reader = GGUFReader(MODEL_PATH)
        
        # Get architecture
        arch_field = reader.fields.get("general.architecture")
        arch = "llama"
        if arch_field:
            arch = arch_field.parts[-1].tobytes().decode("utf-8")
        print(f"Architecture: {arch}")
        
        # Get EOS token ID
        eos_id = -1
        if "tokenizer.ggml.eos_token_id" in reader.fields:
            eos_id = reader.fields["tokenizer.ggml.eos_token_id"].parts[-1][0]
        print(f"EOS Token ID: {eos_id}")

        # Get Chat Template
        if "tokenizer.chat_template" in reader.fields:
            template = reader.fields["tokenizer.chat_template"].parts[-1].tobytes().decode("utf-8")
            print(f"Chat Template found in GGUF:\n{template}")
        else:
            print("No chat template found in GGUF.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_gguf()
