#!/bin/bash
#SBATCH --job-name=confessit-finetune
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=logs/finetune-%j.out
#SBATCH --error=logs/finetune-%j.err

set -euo pipefail

# Load env (adjust to your cluster's module system)
# module load python/3.10 cuda/12.1

# Create venv if needed
if [ ! -d "venv" ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install unsloth
    pip install git+https://github.com/unslothai/unsloth.git
    pip install transformers datasets accelerate peft trl bitsandbytes huggingface_hub
else
    source venv/bin/activate
fi

# Copy data to local SSD if available (faster I/O)
# if [ -d "$TMPDIR" ]; then
#     cp confessions.jsonl "$TMPDIR/"
#     DATA="$TMPDIR/confessions.jsonl"
# else
#     DATA="confessions.jsonl"
# fi

DATA="confessions.jsonl"

# Make sure the jsonl is present
if [ ! -f "$DATA" ]; then
    echo "Error: $DATA not found. Run export_training_data.py first."
    exit 1
fi

mkdir -p logs

python3 finetune_confessit.py \
    --data "$DATA" \
    --output "./outputs" \
    --model "unsloth/Qwen2.5-7B-bnb-4bit" \
    --epochs 3 \
    --lr 2e-4 \
    --batch-size 2 \
    --grad-accum 4 \
    --max-seq-length 512 \
    --lora-r 16 \
    --seed 42 \
    ${HF_TOKEN:+--hf-token "$HF_TOKEN"} \
    ${HF_REPO:+--hf-repo "$HF_REPO"}

echo "Done."