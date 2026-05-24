#!/usr/bin/env python3
"""Append <|endoftext|> to every training example so the model learns to stop.

Usage:
    python3 fix_data_eos.py                    # fixes confessions.jsonl in-place
    python3 fix_data_eos.py --input old.jsonl --output fixed.jsonl  # keeps original
"""

import argparse
import json

EOS = "<|endoftext|>"


def parse_args():
    parser = argparse.ArgumentParser(description="Add EOS tokens to training data")
    parser.add_argument("--input", default="./confessions.jsonl",
                        help="Input JSONL file (default: ./confessions.jsonl)")
    parser.add_argument("--output", default=None,
                        help="Output file (default: overwrite input)")
    return parser.parse_args()


def main():
    args = parse_args()
    in_path = args.input
    out_path = args.output or in_path

    lines = 0
    with open(in_path) as f:
        for line in f:
            if line.strip():
                lines += 1

    print(f"[*] Reading {lines} examples from: {in_path}")
    print(f"[*] Output: {out_path}")

    fixed = 0
    missing = 0
    with open(in_path) as fin, open(out_path, "w") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            text = obj["text"]
            if text.endswith(EOS):
                missing += 1
            else:
                obj["text"] = text + EOS
                fixed += 1
            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")

    print(f"[*] Fixed: {fixed}  |  Already had EOS: {missing}")
    print("[*] Done.")


if __name__ == "__main__":
    main()