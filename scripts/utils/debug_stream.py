import sys
from llama_cpp import Llama

MODEL_PATH = r"m:\Flame-System\witness-forge\models\gpt-oss-20b-uncensored-bf16-Q4_K_M-GGUF\gpt-oss-20b-uncensored-bf16-q4_k_m.gguf"

def debug_streaming():
    print("Loading model...")
    llm = Llama(
        model_path=MODEL_PATH,
        n_ctx=2048,
        n_gpu_layers=-1,
        verbose=False
    )
    
    prompt = "<|im_start|>system\nYou are helpful.<|im_end|>\n<|im_start|>user\nHi<|im_end|>\n<|im_start|>assistant\n"
    
    print(f"\nPrompt: {prompt}")
    print("\nStreaming chunks:")
    print("=" * 60)
    
    stop_tokens = ["<|im_end|>", "SYSTEM:", "USER:"]
    
    stream = llm.create_completion(
        prompt,
        max_tokens=50,
        temperature=0.7,
        stream=True,
        stop=stop_tokens,
    )
    
    chunk_count = 0
    for chunk in stream:
        chunk_count += 1
        print(f"\n--- Chunk {chunk_count} ---")
        print(f"Full chunk: {chunk}")
        
        choices = chunk.get("choices", [])
        if choices:
            choice = choices[0]
            text = choice.get("text", "")
            finish_reason = choice.get("finish_reason")
            print(f"Text: '{text}'")
            print(f"finish_reason: {finish_reason}")
            
            if finish_reason:
                print(f"\n!!! finish_reason detected: {finish_reason}")
                print("Breaking loop...")
                break
        
        if chunk_count > 100:
            print("\n!!! Safety limit reached (100 chunks), breaking...")
            break
    
    print(f"\n{'=' * 60}")
    print(f"Total chunks: {chunk_count}")

if __name__ == "__main__":
    debug_streaming()
