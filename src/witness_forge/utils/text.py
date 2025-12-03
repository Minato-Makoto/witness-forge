def clamp_decoding(d: dict) -> dict:
    d["temperature"] = max(0.1, min(1.5, float(d.get("temperature", 0.7))))
    d["top_p"] = max(0.5, min(0.99, float(d.get("top_p", 0.9))))
    d["max_new_tokens"] = int(max(32, min(2048, d.get("max_new_tokens", 512))))
    d["frequency_penalty"] = float(d.get("frequency_penalty", 0.2))
    d["presence_penalty"] = float(d.get("presence_penalty", 0.0))
    default_rep = 1.0 + max(0.0, d.get("frequency_penalty", 0.0))
    d["repetition_penalty"] = max(1.0, min(2.0, float(d.get("repetition_penalty", default_rep))))
    d["no_repeat_ngram_size"] = max(0, int(d.get("no_repeat_ngram_size", 0)))
    return d
