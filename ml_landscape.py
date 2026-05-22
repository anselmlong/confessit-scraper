#!/usr/bin/env python3
"""
Embedding landscape analysis for ConfessIt.
- UMAP 2D projection of all confession embeddings
- HDBSCAN clustering
- Cluster profiling by category, virality, time
- Outputs: visualization + console report
"""

import re, sqlite3, json
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="darkgrid", font_scale=0.9)

DB_PATH = Path("data/messages.db")
EMBED_PATH = Path("data/embeddings_v5.npy")
EMBED_IDS_PATH = Path("data/embedding_ids_v5.npy")
OUT_DIR = Path("reports/landscape")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── 1. Data ──────────────────────────────────────────────────────────────────

print("Loading embeddings...", flush=True)
embeddings = np.load(EMBED_PATH).astype(np.float64)
embed_ids = np.load(EMBED_IDS_PATH)
print(f"  {embeddings.shape}, norm={np.linalg.norm(embeddings, axis=1).mean():.3f}", flush=True)

print("Loading posts from DB...", flush=True)
conn = sqlite3.connect(str(DB_PATH))
rows = conn.execute("""
    SELECT id, text, reactions_count, reply_count, forwards, date, category
    FROM messages WHERE is_reply=0
""").fetchall()
conn.close()
id_map = {r[0]: r for r in rows}
print(f"  {len(rows)} posts in DB", flush=True)

# Align: only posts with embeddings
texts, cats, scores, dates = [], [], [], []
missing = 0
for eid in embed_ids:
    r = id_map.get(int(eid))
    if r:
        # extract clean body
        t = r[1] or ""
        m = re.search(r"---\s*\n(.*?)\n---", t, re.DOTALL)
        body = m.group(1).strip() if m else ""
        if not body or len(body) < 20:
            body = t.strip()[:200]
        texts.append(body)
        cats.append((r[6] or "unknown").lower())
        score = r[2]*1 + r[3]*2 + r[4]*3
        scores.append(score)
        dates.append(r[5] or "")
    else:
        missing += 1
        texts.append("")
        cats.append("unknown")
        scores.append(0)
        dates.append("")
print(f"  {missing} embedding IDs missing from DB", flush=True)

# Virality label (top 25%)
arr_scores = np.array(scores)
thresh = np.percentile(arr_scores, 75)
viral = (arr_scores >= thresh).astype(int)
print(f"  Viral rate: {viral.mean():.1%} (threshold={thresh:.0f})", flush=True)

# ── 2. UMAP ──────────────────────────────────────────────────────────────────

print("\nRunning UMAP (65k points, 512d → 2d)...", flush=True)
from umap import UMAP
# sample 15k for fit, then transform all (balance speed vs quality)
rng = np.random.RandomState(42)
sample_idx = rng.choice(len(embeddings), min(15000, len(embeddings)), replace=False)
reducer = UMAP(n_neighbors=30, min_dist=0.1, n_components=2,
               random_state=42, n_jobs=1, verbose=True)
reducer.fit(embeddings[sample_idx])
print("  Transforming all points...", flush=True)
proj = reducer.transform(embeddings)  # (N, 2)
print(f"  Done: proj shape={proj.shape}", flush=True)

# ── 3. HDBSCAN ───────────────────────────────────────────────────────────────

print("\nClustering with HDBSCAN...", flush=True)
from hdbscan import HDBSCAN
clusterer = HDBSCAN(min_cluster_size=200, min_samples=50,
                    metric="euclidean", prediction_data=True)
cluster_labels = clusterer.fit_predict(proj)
n_clusters = len(set(cluster_labels) - {-1})
n_noise = (cluster_labels == -1).sum()
print(f"  Clusters: {n_clusters}, Noise points: {n_noise} ({n_noise/len(cluster_labels):.1%})", flush=True)

# ── 4. Plot ──────────────────────────────────────────────────────────────────

print("\nGenerating plots...", flush=True)

fig, axes = plt.subplots(2, 2, figsize=(18, 16))

# A) Cluster map (colored by cluster)
ax = axes[0, 0]
cmap = plt.cm.tab20
colors = [cmap(c % 20) if c >= 0 else (0.6, 0.6, 0.6, 0.3) for c in cluster_labels]
sc = ax.scatter(proj[:, 0], proj[:, 1], c=colors, s=2, alpha=0.5, rasterized=True)
ax.set_title(f"HDBSCAN Clusters ({n_clusters} clusters, {n_noise} noise)", fontsize=13)
ax.set_xlabel("UMAP 1")
ax.set_ylabel("UMAP 2")
ax.set_aspect("equal")

# B) Category map
ax = axes[0, 1]
cat_colors = {"academics": "#1f77b4", "social": "#ff7f0e", "mental health": "#d62728",
              "career": "#2ca02c", "accommodation": "#9467bd", "food": "#8c564b",
              "unknown": "#cccccc"}
for cat in set(cats):
    mask = np.array([c == cat for c in cats])
    if mask.sum() < 50:
        continue
    c = cat_colors.get(cat, "#333333")
    ax.scatter(proj[mask, 0], proj[mask, 1], c=c, s=2, alpha=0.4,
               label=f"{cat} ({mask.sum():,})", rasterized=True)
ax.set_title("Categories in Embedding Space", fontsize=13)
ax.legend(markerscale=5, fontsize=8, loc="upper right")
ax.set_aspect("equal")

# C) Virality map
ax = axes[1, 0]
for vl, label, color in [(0, "Not viral", "#cccccc"), (1, "Viral", "#e74c3c")]:
    mask = viral == vl
    ax.scatter(proj[mask, 0], proj[mask, 1], c=color, s=2, alpha=0.3 if vl == 0 else 0.6,
               label=f"{label} ({mask.sum():,})", rasterized=True)
ax.set_title("Virality Distribution", fontsize=13)
ax.legend(markerscale=5, fontsize=10)
ax.set_aspect("equal")

# D) Density map
ax = axes[1, 1]
ax.hexbin(proj[:, 0], proj[:, 1], gridsize=80, cmap="Blues", mincnt=1, rasterized=True)
ax.set_title("Point Density (hexbin)", fontsize=13)
ax.set_aspect("equal")

plt.tight_layout()
plot_path = OUT_DIR / "landscape.png"
plt.savefig(plot_path, dpi=200, bbox_inches="tight")
plt.close()
print(f"  Saved: {plot_path}", flush=True)

# ── 5. Cluster profiles ─────────────────────────────────────────────────────

print("\n=== Cluster Profiles ===", flush=True)
cluster_info = []
for cid in range(n_clusters):
    mask = cluster_labels == cid
    n = mask.sum()
    if n < 50:
        continue

    # Category breakdown
    cats_in = [cats[i] for i in np.where(mask)[0]]
    cat_dist = pd.Series(cats_in).value_counts()
    top_cat = cat_dist.index[0] if len(cat_dist) > 0 else "?"
    cat_pct = cat_dist.iloc[0] / n * 100 if len(cat_dist) > 0 else 0

    # Virality
    viral_rate = viral[mask].mean()

    # Centrality: mean distance to cluster center
    center = proj[mask].mean(axis=0)
    dists = np.linalg.norm(proj[mask] - center, axis=1)
    spread = dists.mean()

    # Top keywords (TF-IDF style: most distinctive words)
    cluster_texts = [texts[i] for i in np.where(mask)[0]]
    all_words = " ".join(cluster_texts).lower().split()
    word_counts = pd.Series(all_words).value_counts()
    # Filter common stopwords
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                 "to", "of", "in", "for", "on", "with", "at", "by", "from",
                 "and", "or", "but", "if", "so", "as", "it", "its", "i", "my",
                 "me", "we", "you", "your", "he", "she", "they", "this", "that",
                 "do", "dont", "does", "did", "have", "has", "had", "not", "no",
                 "just", "like", "get", "got", "can", "will", "would", "could",
                 "should", "know", "think", "feel", "really", "also", "even",
                 "still", "much", "many", "some", "any", "all", "very"}
    top_words = [w for w in word_counts.index if w not in stopwords and len(w) > 3][:8]

    cluster_info.append({
        "id": cid,
        "size": n,
        "pct": n / len(cluster_labels) * 100,
        "top_cat": f"{top_cat} ({cat_pct:.0f}%)",
        "viral_rate": viral_rate,
        "spread": spread,
        "top_words": ", ".join(top_words),
    })

cluster_info.sort(key=lambda x: x["size"], reverse=True)
print(f"{'#':>3} {'Size':>7} {'%':>5} {'Top Category':<25} {'Viral%':>7} {'Spread':>7}  Keywords")
print("-" * 95)
for ci in cluster_info:
    print(f"{ci['id']:>3} {ci['size']:>7} {ci['pct']:>4.0f}% {ci['top_cat']:<25} {ci['viral_rate']:>6.1%} {ci['spread']:>6.2f}  {ci['top_words']}")

# ── 6. Interesting findings ─────────────────────────────────────────────────

print("\n=== Key Observations ===", flush=True)

# Viral hotspots: regions with highest viral density
from scipy.spatial import KDTree
tree = KDTree(proj)
# For each viral post, find nearby viral ratio
k = 100
viral_idx = np.where(viral == 1)[0]
n_test = min(5000, len(viral_idx))
hotspots = []
for idx in np.random.choice(viral_idx, n_test, replace=False):
    dists_nn, nn_idx = tree.query(proj[idx], k=k)
    viral_frac = viral[nn_idx].mean()
    if viral_frac > 0.40:  # significantly above average
        hotspots.append((viral_frac, idx))

hotspots.sort(reverse=True)
if hotspots:
    top_hotspots = hotspots[:5]
    print("\nTop viral hotspots (pockets where >40% of nearby posts are viral):")
    for vf, idx in top_hotspots:
        t = texts[idx][:120]
        print(f"  {vf:.0%} viral nearby — \"{t}...\"")
        print(f"    cat={cats[idx]}, score={scores[idx]}")

# Most representative post per cluster (closest to cluster center)
print("\nMost central post per cluster:")
for ci in cluster_info[:8]:
    mask = cluster_labels == ci["id"]
    center = proj[mask].mean(axis=0)
    dists = np.linalg.norm(proj[mask] - center, axis=1)
    best = np.argmin(dists)
    global_idx = np.where(mask)[0][best]
    t = texts[global_idx][:150]
    print(f"  Cluster {ci['id']} ({ci['size']:,}) — \"{t}...\"")
    print(f"    top words: {ci['top_words']}")

# Outlier posts: farthest from any cluster center
print("\nMost unique posts (farthest from cluster centers):")
noise_mask = cluster_labels == -1
if noise_mask.sum() > 0:
    noise_idx = np.where(noise_mask)[0]
    # farthest from any other point
    far_dists = []
    for idx in noise_idx[:1000]:
        dists_nn, _ = tree.query(proj[idx], k=10)
        far_dists.append((dists_nn[-1], idx))
    far_dists.sort(reverse=True)
    for d, idx in far_dists[:5]:
        t = texts[idx][:120]
        print(f"  distance~{d:.2f} — \"{t}...\"")
        print(f"    cat={cats[idx]}, score={scores[idx]}")

print(f"\nPlots saved to {plot_path}", flush=True)