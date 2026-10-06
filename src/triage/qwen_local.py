"""Load Qwen2.5-0.5B-Instruct with the LoRA adapter and generate triage JSON.

Works on CPU (local code, the Space) and on GPU (the Colab notebook). torch, transformers and
peft are imported inside the functions so the rest of the package does not need them.
"""

from triage.prompts import finetuned_messages

BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
ADAPTER_REPO = "Khalid-Mehmood-117/qwen2.5-0.5b-ticket-triage-lora"
MAX_NEW_TOKENS = 128


def load_model(adapter: str | None = ADAPTER_REPO, base_model: str = BASE_MODEL,
               device: str | None = None, token: str | None = None):
    """Return (model, tokenizer). adapter=None loads the base model only."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    dtype = torch.float16 if device == "cuda" else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(base_model, token=token)
    tokenizer.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(base_model, dtype=dtype, token=token).to(device)
    if adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, adapter, token=token)
    model.eval()
    return model, tokenizer


def generate(model, tokenizer, tickets: list[str], batch_size: int = 8,
             max_new_tokens: int = MAX_NEW_TOKENS, sample: bool = False, seed: int = 0) -> list[str]:
    """Greedy decoding by default; sample=True uses temperature 0.3 with a fixed seed (the retry)."""
    import torch

    tokenizer.padding_side = "left"
    outputs = []
    for start in range(0, len(tickets), batch_size):
        batch = tickets[start:start + batch_size]
        prompts = [tokenizer.apply_chat_template(finetuned_messages(t), tokenize=False,
                                                 add_generation_prompt=True) for t in batch]
        inputs = tokenizer(prompts, return_tensors="pt", padding=True).to(model.device)
        options = {"do_sample": False}
        if sample:
            torch.manual_seed(seed)
            options = {"do_sample": True, "temperature": 0.3, "top_p": 1.0}
        with torch.no_grad():
            generated = model.generate(**inputs, max_new_tokens=max_new_tokens,
                                       pad_token_id=tokenizer.pad_token_id, **options)
        new_tokens = generated[:, inputs["input_ids"].shape[1]:]
        outputs += tokenizer.batch_decode(new_tokens, skip_special_tokens=True)
    return outputs
