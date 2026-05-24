#!/bin/bash
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:15:00
#SBATCH --job-name=confessit-infer
#SBATCH --output=confessit-infer-%j.out

set -e

# Load env (adjust to your cluster setup)
# module load python/3.13

PROMPT="${1:-"I have a secret that I've never told anyone"}"
NUM="${2:-5}"

python3 inference.py \
    --prompt "$PROMPT" \
    --num "$NUM" \
    --max-new 256 \
    --temp 0.8 \
    --output "confessit-results-$(date +%s).txt"