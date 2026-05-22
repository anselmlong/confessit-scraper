#!/bin/bash
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --job-name=confessit-eos

set -e

cd ~/confessit-scraper

# Step 1: fix the data
python3 fix_data_eos.py --input confessions.jsonl --output confessions_eos.jsonl

# Step 2: continued training
source venv/bin/activate
python3 train_eos.py \
    --data confessions_eos.jsonl \
    --epochs 0.5 \
    --lr 1e-4 \
    --hf-repo anselmlong/confessit \
    --hf-token $HF_TOKEN \
    --output ./outputs_eos