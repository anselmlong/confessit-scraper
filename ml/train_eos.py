#!/usr/bin/env python3
"""Continued training to teach the model the EOS token.

Run this after fix_data_eos.py. It does 1 epoch of LoRA training on the
fixed data (with <|endoftext|> appended to every example), then pushes the
updated adapter to HuggingFace.

Usage:
    # Fix data first
    python3 fix_data_eos.py

    # Continued training (1 epoch on fixed data)
    python3 train_eos.py --hf-token hf_xxxxx

    # Or with options
    python3 train_eos.py \
        --data confessions_fixed.jsonl \
        --hf-repo anselmlong/confessit \
        --hf-token hf_xxxxx \
        --epochs 0.5 \
        --lr 1e-4 \
        --output ./outputs_eos

SLURM:
    sbatch train_eos.sbatch
"""

import argparse
import os
import sys

import torch
from datasets import load_dataset
from peft import PeftModel
from transformers import TrainingArguments
from trl import SFTTrainer
from unsloth import FastLanguageModel, is_bfloat16_supported


def parse_args():
    parser = argparse.ArgumentParser(description="ConfessIt EOS continued training")
    parser.add_argument("--data", default="./confessions.jsonl",
                        help="Path to fixed JSONL (run fix_data_eos.py first)")
    parser.add_argument("--model", default="unsloth/Qwen2.5-7B-bnb-4bit",
                        help="Base model")
    parser.add_argument("--adapter", default="anselmlong/confessit",
                        help="Existing LoRA adapter on HF to continue from")
    parser.add_argument("--output", default="./outputs_eos",
                        help="Checkpoint directory")
    parser.add_argument("--epochs", type=float, default=0.5,
                        help="Epochs (default: 0.5 — just enough for EOS)")
    parser.add_argument("--lr", type=float, default=1e-4,
                        help="Learning rate (default: 1e-4, lower than initial training)")
    parser.add_argument("--batch-size", type=int, default=2,
                        help="Per-device batch size")
    parser.add_argument("--grad-accum", type=int, default=4,
                        help="Gradient accumulation steps")
    parser.add_argument("--max-seq-length", type=int, default=512,
                        help="Max sequence length")
    parser.add_argument("--hf-token", default=None,
                        help="HF token for pushing")
    parser.add_argument("--hf-repo", default="anselmlong/confessit",
                        help="HF repo to push updated adapter to")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("  ConfessIt — Continued Training (EOS fix)")
    print("=" * 60)

    # 1. Load data
    print(f"[*] Loading data: {args.data}")
    dataset = load_dataset("json", data_files=args.data, split="train")

    # 2. Load base model + existing adapter
    print(f"[*] Loading base model: {args.model}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model,
        max_seq_length=args.max_seq_length,
        dtype=None,
        load_in_4bit=True,
    )

    print(f"[*] Loading existing adapter: {args.adapter}")
    model = PeftModel.from_pretrained(model, args.adapter)

    # 3. Training args — short and sweet
    training_args = TrainingArguments(
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        warmup_steps=5,
        learning_rate=args.lr,
        fp16=not is_bfloat16_supported(),
        bf16=is_bfloat16_supported(),
        logging_steps=10,
        eval_strategy="no",
        save_strategy="epoch",
        output_dir=args.output,
        report_to="none",
        num_train_epochs=args.epochs,
        seed=args.seed,
        ddp_find_unused_parameters=False,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=training_args,
        dataset_text_field="text",
        max_seq_length=args.max_seq_length,
    )

    print(f"[*] Starting continued training ({args.epochs} epoch(s))...")
    trainer.train()
    print("[*] Training complete!")

    # 4. Save + push updated adapter
    final_dir = os.path.join(args.output, "final_adapter")
    model.save_pretrained(final_dir)
    tokenizer.save_pretrained(final_dir)
    print(f"[*] Saved to: {final_dir}")

    if args.hf_token:
        print(f"[*] Pushing updated adapter to HF: {args.hf_repo}")
        model.push_to_hub(args.hf_repo, token=args.hf_token)
        tokenizer.push_to_hub(args.hf_repo, token=args.hf_token)
        print(f"[*] Pushed to: https://huggingface.co/{args.hf_repo}")
    else:
        print("[*] No --hf-token, skipping push.")

    print("[*] Done.")


if __name__ == "__main__":
    main()