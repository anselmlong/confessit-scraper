# ConfessIt — Unsloth Fine-Tuning

Fine-tune Qwen 2.5 7B on NUS confessions via QLoRA.

## Files

| File | Purpose |
|------|---------|
| `export_training_data.py` | Export script — pulls posts from SQLite, strips metadata & template noise, outputs `{"text": "..."}` JSONL |
| `data/confessions.jsonl` | 9,189 posts (reply_count >= 6), clean body text, zero bot boilerplate |
| `unsloth-finetune.ipynb` | Colab-ready notebook: upload → train → push to HuggingFace Hub |

## Data Pipeline

1. `sqlite3 data/messages.db` — `messages` table, uses `content` column (clean body) or falls back to `text`
2. Filters: reply_count >= 6, length 20–2000, alpha ratio >= 0.3
3. Strips bot template footer (✍️/🫣 Click here / PM Confessor / 👇 Comment below)
4. Outputs causal LM format — `{"text": "..."}` — no chat templates

Run: `python3 export_training_data.py`

## Training Config

- **Model:** `unsloth/Qwen2.5-7B-bnb-4bit`
- **Format:** Causal LM (single `text` field, no system/user/assistant)
- **LoRA:** rank 16, alpha 16, target all linear proj layers
- **Batch:** 2 per device, grad accum 4 (effective 8)
- **LR:** 2e-4, 3 epochs
- **Context:** 512 tokens (confessions are short)
- **Runtime:** ~40 min on Colab T4

## Export

- **Adapter (~16 MB)** → `model.push_to_hub(repo_id, tokenizer=tokenizer)`
- **Merged 16-bit (~4 GB)** → `model.save_pretrained_merged()` + optional HF push

## Notebook Sections

1. Install deps
2. Upload `confessions.jsonl`
3. Dataset split + stats
4. Load 4-bit base model
5. Inject LoRA
6. Train (SFTTrainer)
7. Inference demo (4 seed prompts)
8. Push adapter to HuggingFace Hub
9. Usage examples (adapter load + merged model + GGUF)