#!/usr/bin/env python3
"""
ConfessIt — inference script for the fine-tuned confessit model.

Loads the Unsloth Qwen 2.5 7B + LoRA adapter from HuggingFace and generates
confession-style text. Requires a GPU with ~8GB+ VRAM.

Usage:
    # Interactive mode (type prompts, get confessions)
    python3 inference.py

    # One-shot generation
    python3 inference.py --prompt "I have a secret that"

    # Multiple samples from one prompt
    python3 inference.py --prompt "I've never told anyone this" --num 3

    # Tweak generation
    python3 inference.py --prompt "Sometimes I pretend" --temp 0.9 --max-new 512

    # Save output to file
    python3 inference.py --prompt "I'm afraid that" --num 5 --output results.txt

    # On SLURM (batch)
    srun --gres=gpu:1 --cpus-per-task=4 --mem=16G --time=00:10:00 \
        python3 inference.py --prompt "I secretly" --num 5 --output results.txt

    # On SLURM (interactive)
    srun --gres=gpu:1 --cpus-per-task=4 --mem=16G --time=01:00:00 \
        python3 inference.py

Dependencies (same env as training):
    pip install unsloth transformers peft accelerate bitsandbytes safetensors
"""

import argparse
import os
import sys
import time

import unsloth  # noqa: F401 — ensures torch is available before explicit import
import torch
from peft import PeftModel
from transformers import StoppingCriteria, StoppingCriteriaList
from unsloth import FastLanguageModel, is_bfloat16_supported


def parse_args():
    parser = argparse.ArgumentParser(description="ConfessIt inference")
    parser.add_argument("--prompt", default=None,
                        help="Seed prompt (omit for interactive mode)")
    parser.add_argument("--num", type=int, default=1,
                        help="Generations per prompt (default: 1)")
    parser.add_argument("--max-new", type=int, default=256,
                        help="Max new tokens to generate (default: 256)")
    parser.add_argument("--temp", type=float, default=0.8,
                        help="Temperature, higher = more random (default: 0.8)")
    parser.add_argument("--top-p", type=float, default=0.9,
                        help="Top-p nucleus sampling (default: 0.9)")
    parser.add_argument("--top-k", type=int, default=40,
                        help="Top-k (0 = disabled, default: 40)")
    parser.add_argument("--no-repeat", type=float, default=2.0,
                        help="Repeat penalty (1.0 = disabled, default: 2.0)")
    parser.add_argument("--output", default=None,
                        help="Save generations to file")
    parser.add_argument("--model", default="unsloth/Qwen2.5-7B-bnb-4bit",
                        help="Base model on HF (default: unsloth/Qwen2.5-7B-bnb-4bit)")
    parser.add_argument("--adapter", default="anselmlong/confessit",
                        help="LoRA adapter on HF (default: anselmlong/confessit)")
    parser.add_argument("--no-garbage-stop", action="store_true",
                        help="Disable automatic garbage detection (default: on)")
    parser.add_argument("--max-seq-len", type=int, default=1024,
                        help="Max sequence length (default: 1024)")
    return parser.parse_args()


class EndOfConfessionCriteria(StoppingCriteria):
    """Stop generation when output devolves into emoji/punctuation garbage.

    The model was trained without EOS tokens in the data, so it doesn't know
    when to stop. Once the confession is done, it tends to ramble into emoji
    soup. This criteria detects that by checking if the last ~20 generated
    tokens are mostly non-alphanumeric characters.
    """
    def __init__(self, tokenizer, window=20, alpha_threshold=0.25):
        super().__init__()
        self.tokenizer = tokenizer
        self.window = window
        self.alpha_threshold = alpha_threshold

    def __call__(self, input_ids, scores, **kwargs):
        generated = input_ids[0]
        if len(generated) < self.window:
            return False

        text = self.tokenizer.decode(generated[-self.window:], skip_special_tokens=True)
        if not text.strip():
            return False

        alpha = sum(1 for c in text if c.isalpha())
        return (alpha / len(text.rstrip())) < self.alpha_threshold


def load_model(model_name, adapter_name, max_seq_len):
    """Load 4-bit base model + LoRA adapter via Unsloth + PEFT."""
    print(f"[*] Loading base model: {model_name}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=max_seq_len,
        dtype=None,
        load_in_4bit=True,
    )

    print(f"[*] Loading LoRA adapter: {adapter_name}")
    model = PeftModel.from_pretrained(model, adapter_name)
    FastLanguageModel.for_inference(model)

    if torch.cuda.is_available():
        free, _ = torch.cuda.mem_get_info(0)
        print(f"[*] VRAM free: {free / 1e9:.1f} GB")
    else:
        print("[!] No GPU detected — CPU with 7B will be unusably slow")

    return model, tokenizer


def generate(model, tokenizer, prompt, args, stopping_criteria=None):
    """Generate completions from a prompt."""
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    gen_kwargs = dict(
        **inputs,
        max_new_tokens=args.max_new,
        temperature=args.temp if args.temp > 0 else None,
        top_p=args.top_p,
        top_k=args.top_k if args.top_k > 0 else None,
        repetition_penalty=args.no_repeat if args.no_repeat != 1.0 else None,
        do_sample=args.temp > 0,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )
    if stopping_criteria is not None:
        gen_kwargs["stopping_criteria"] = stopping_criteria

    outputs = model.generate(**gen_kwargs)

    results = []
    for output in outputs:
        text = tokenizer.decode(
            output[inputs["input_ids"].shape[1]:],
            skip_special_tokens=True,
        ).strip()
        results.append(text)

    return results


def main():
    args = parse_args()

    if not torch.cuda.is_available():
        print("[!] WARNING: No GPU detected. This script needs a GPU.")
        print("    On SLURM: srun --gres=gpu:1 ...")
        print("    Exiting.\n")
        sys.exit(1)

    print("=" * 60)
    print("  ConfessIt — Inference")
    print("=" * 60)
    print(f"  Base:    {args.model}")
    print(f"  Adapter: {args.adapter}")
    print(f"  GPU:     {torch.cuda.get_device_name(0)}")
    print("=" * 60)

    model, tokenizer = load_model(args.model, args.adapter, args.max_seq_len)

    # Build garbage-detection stopping criteria (unless disabled)
    garbage_stop = None
    if not args.no_garbage_stop:
        garbage_stop = StoppingCriteriaList([EndOfConfessionCriteria(tokenizer)])
    else:
        print("[*] Garbage detection disabled (--no-garbage-stop)")

    output_lines = []

    if args.prompt:
        prompts = [args.prompt]
    else:
        print("\n[*] Interactive mode — type a prompt, get a confession.")
        print("    Type 'quit' or 'q' to exit.\n")
        prompts = None

    if prompts:
        for prompt in prompts:
            print(f"\n── Prompt ──\n{prompt}")
            results = generate(model, tokenizer, prompt, args, garbage_stop)
            for i, text in enumerate(results):
                line = f"\n── Generation {i+1} ──\n{prompt}{text}"
                print(line)
                output_lines.append(line)
    else:
        while True:
            try:
                prompt = input("prompt> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not prompt or prompt.lower() in ("quit", "q", "exit"):
                break

            t0 = time.time()
            results = generate(model, tokenizer, prompt, args, garbage_stop)
            elapsed = time.time() - t0

            for i, text in enumerate(results):
                line = f"\n── Gen {i+1} ({elapsed:.1f}s) ──\n{prompt}{text}"
                print(line)
                output_lines.append(line)

    if args.output:
        with open(args.output, "w") as f:
            f.write("\n".join(output_lines))
        print(f"\n[*] Saved to: {args.output}")

    print("\n[*] Done.")


if __name__ == "__main__":
    main()
