#!/usr/bin/env python3
"""
ConfessIt — Unsloth Fine-Tuning (SLURM-ready)

Fine-tune Qwen 2.5 7B on NUS confession-style posts using QLoRA.

Usage:
    # Default (reads ./confessions.jsonl)
    python3 finetune_confessit.py

    # With all options
    python3 finetune_confessit.py \
        --data ./data/confessions.jsonl \
        --output ./outputs \
        --model unsloth/Qwen2.5-7B-bnb-4bit \
        --epochs 3 \
        --lr 2e-4 \
        --batch-size 2 \
        --grad-accum 4 \
        --max-seq-length 512 \
        --lora-r 16 \
        --hf-token hf_xxxxx \
        --hf-repo your-username/confessit-qwen-2.5-7b-lora \
        --seed 42

SLURM example (sbatch script):
    #SBATCH --gres=gpu:1
    #SBATCH --cpus-per-task=8
    #SBATCH --mem=32G
    #SBATCH --time=04:00:00

    module load python/3.13
    python3 -m venv venv
    source venv/bin/activate
    pip install unsloth transformers datasets accelerate peft trl bitsandbytes
    python3 finetune_confessit.py --data confessions.jsonl --hf-token $HF_TOKEN
"""

import argparse
import os
import sys

import torch
from unsloth import FastLanguageModel, is_bfloat16_supported
from datasets import load_dataset
from transformers import TrainingArguments
from trl import SFTTrainer


def parse_args():
    parser = argparse.ArgumentParser(description="ConfessIt Unsloth Fine-Tuning")
    parser.add_argument("--data", default="./confessions.jsonl",
                        help="Path to JSONL dataset (format: {\"text\": \"...\"} per line)")
    parser.add_argument("--model", default="unsloth/Qwen2.5-7B-bnb-4bit",
                        help="Base model name on HF Hub")
    parser.add_argument("--output", default="./outputs",
                        help="Directory for training checkpoints")
    parser.add_argument("--epochs", type=int, default=3,
                        help="Number of training epochs")
    parser.add_argument("--lr", type=float, default=2e-4,
                        help="Learning rate")
    parser.add_argument("--batch-size", type=int, default=2,
                        help="Per-device batch size")
    parser.add_argument("--grad-accum", type=int, default=4,
                        help="Gradient accumulation steps (effective batch = batch_size * grad_accum)")
    parser.add_argument("--max-seq-length", type=int, default=512,
                        help="Maximum sequence length for tokenization")
    parser.add_argument("--lora-r", type=int, default=16,
                        help="LoRA rank")
    parser.add_argument("--lora-alpha", type=int, default=16,
                        help="LoRA alpha")
    parser.add_argument("--lora-dropout", type=float, default=0.0,
                        help="LoRA dropout")
    parser.add_argument("--warmup-steps", type=int, default=10,
                        help="Warmup steps for scheduler")
    parser.add_argument("--eval-steps", type=int, default=50,
                        help="Evaluate every N steps")
    parser.add_argument("--logging-steps", type=int, default=10,
                        help="Log every N steps")
    parser.add_argument("--save-strategy", default="epoch",
                        choices=["epoch", "steps", "no"],
                        help="Checkpoint save strategy")
    parser.add_argument("--test-size", type=float, default=0.05,
                        help="Fraction of data to hold out for evaluation")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed")
    parser.add_argument("--hf-token", default=None,
                        help="HuggingFace token for pushing adapter to Hub")
    parser.add_argument("--hf-repo", default=None,
                        help="HF Hub repo to push adapter to (e.g. username/repo-name)")
    parser.add_argument("--no-eval", action="store_true",
                        help="Skip evaluation split (use all data for training)")
    parser.add_argument("--report-to", default="none",
                        choices=["none", "wandb", "tensorboard"],
                        help="Experiment tracking backend")
    return parser.parse_args()


def load_and_prepare_data(data_path, test_size, seed, no_eval):
    """Load JSONL dataset and split into train/eval."""
    print(f"[*] Loading dataset from: {data_path}")
    dataset = load_dataset("json", data_files=data_path, split="train")

    if no_eval or test_size == 0:
        print(f"[*] Using all {len(dataset)} examples for training (no eval split)")
        return dataset, None
    else:
        split = dataset.train_test_split(test_size=test_size, seed=seed)
        train_dataset = split["train"]
        eval_dataset = split["test"]
        print(f"[*] Train: {len(train_dataset)}  |  Eval: {len(eval_dataset)}")

        # Print stats
        lengths = [len(r["text"]) for r in train_dataset]
        lengths.sort()
        print(f"[*] Text length -> min: {lengths[0]}  |  max: {lengths[-1]}  |  "
              f"median: {lengths[len(lengths)//2]}")

        return train_dataset, eval_dataset


def load_model(model_name, max_seq_length):
    """Load base model with 4-bit quantization."""
    print(f"[*] Loading model: {model_name}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=max_seq_length,
        dtype=None,
        load_in_4bit=True,
    )

    if torch.cuda.is_available():
        total = torch.cuda.get_device_properties(0).total_memory / 1e9
        free, _ = torch.cuda.mem_get_info(0)
        print(f"[*] GPU: {total:.1f} GB total — {free / 1e9:.1f} GB free")

    return model, tokenizer


def add_lora_adapters(model, r, alpha, dropout, seed):
    """Inject LoRA adapters into the model."""
    model = FastLanguageModel.get_peft_model(
        model,
        r=r,
        lora_alpha=alpha,
        lora_dropout=dropout,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        use_gradient_checkpointing="unsloth",
        random_state=seed,
    )
    print("[*] LoRA adapters injected:")
    model.print_trainable_parameters()
    return model


def train(model, tokenizer, train_dataset, eval_dataset, args):
    """Run SFT training."""
    training_args = TrainingArguments(
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        warmup_steps=args.warmup_steps,
        learning_rate=args.lr,
        fp16=not is_bfloat16_supported(),
        bf16=is_bfloat16_supported(),
        logging_steps=args.logging_steps,
        eval_strategy="steps" if eval_dataset else "no",
        eval_steps=args.eval_steps if eval_dataset else None,
        save_strategy=args.save_strategy,
        output_dir=args.output,
        report_to=args.report_to,
        num_train_epochs=args.epochs,
        push_to_hub=False,
        seed=args.seed,
        ddp_find_unused_parameters=False,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        args=training_args,
        dataset_text_field="text",
        max_seq_length=args.max_seq_length,
    )

    print("[*] Starting training...")
    trainer.train()
    print("[*] Training complete!")

    # Save final adapter locally
    final_dir = os.path.join(args.output, "final_adapter")
    model.save_pretrained(final_dir)
    tokenizer.save_pretrained(final_dir)
    print(f"[*] Adapter saved to: {final_dir}")

    return trainer, final_dir


def push_to_hub(model, tokenizer, repo_id, token):
    """Push LoRA adapter to HuggingFace Hub."""
    print(f"[*] Pushing adapter to HF Hub: {repo_id}")
    model.push_to_hub(repo_id, token=token)
    tokenizer.push_to_hub(repo_id, token=token)
    print(f"[*] Pushed to: https://huggingface.co/{repo_id}")


def main():
    args = parse_args()

    print("=" * 60)
    print("  ConfessIt — Unsloth Fine-Tuning")
    print("=" * 60)
    for key, val in vars(args).items():
        print(f"    {key}: {val}")
    print("=" * 60)

    # Verify dataset exists
    if not os.path.exists(args.data):
        print(f"[!] Dataset not found: {args.data}")
        sys.exit(1)

    # Load data
    train_dataset, eval_dataset = load_and_prepare_data(
        args.data, args.test_size, args.seed, args.no_eval
    )

    # Load model
    model, tokenizer = load_model(args.model, args.max_seq_length)

    # Add LoRA
    model = add_lora_adapters(model, args.lora_r, args.lora_alpha, args.lora_dropout, args.seed)

    # Train
    trainer, adapter_dir = train(model, tokenizer, train_dataset, eval_dataset, args)

    # Push to Hub if requested
    if args.hf_repo and args.hf_token:
        push_to_hub(model, tokenizer, args.hf_repo, args.hf_token)
    elif args.hf_repo and not args.hf_token:
        print("[!] --hf-repo given but no --hf-token. Skipping hub push.")
        print("    Set HF_TOKEN env var or pass --hf-token")

    print("[*] Done.")
    print(f"[*] Adapter: {adapter_dir}")
    if args.hf_repo:
        print(f"[*] Hub:     https://huggingface.co/{args.hf_repo}")


if __name__ == "__main__":
    main()