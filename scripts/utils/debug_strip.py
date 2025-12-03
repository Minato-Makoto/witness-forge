import re

def test_stripping():
    # Simulate witness.py output
    thought_text = "Sure! Here's how I'd respond:\n1. Step 1\n2. Step 2"
    formatted_thought = "\n".join([f"> {line}" for line in thought_text.splitlines()])
    history_text = f"> 💭 **Thinking:**\n{formatted_thought}\n\nHey! Bạn cần giúp gì?"
    
    print("--- History Text (from witness.py) ---")
    print(history_text)
    print("--------------------------------------")

    # Logic from chat_templates.py
    parts = history_text.split("\n\n", 1)
    if len(parts) >= 2:
        first_block = parts[0].strip()
        if first_block.startswith(">") or first_block.lower().startswith("thinking:"):
            print("Detected Thought Block")
            
            # Regex 1: Strip blockquotes
            thought_content = re.sub(r"^>\s?", "", first_block, flags=re.MULTILINE).strip()
            print("\n--- After Strip Blockquotes ---")
            print(thought_content)
            
            # Regex 2: Strip UI Header
            thought_content = re.sub(r"^💭 \*\*Thinking:\*\*\s*", "", thought_content).strip()
            print("\n--- After Strip Header ---")
            print(thought_content)
            
            if thought_content == thought_text:
                print("\nSUCCESS: Content matches original thought.")
            else:
                print("\nFAILURE: Content does NOT match original thought.")
                print("Expected:")
                print(thought_text)
                print("Actual:")
                print(thought_content)

if __name__ == "__main__":
    test_stripping()
