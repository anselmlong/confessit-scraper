#!/usr/bin/env python3
"""Explore the ConfessIT embedding landscape with multiple clustering approaches."""

import re, sqlite3, numpy as np, time
from pathlib import Path
from collections import Counter

# ── Data ────────────────────────────────────────────────────────────

BASE = Path(__file__).parent
proj = np.load(str(BASE / "data/umap_proj.npy"))
eids = np.load(str(BASE / "data/embedding_ids_v5.npy"))

conn = sqlite3.connect(str(BASE / "data/messages.db"))
rows = conn.execute(
    "SELECT id, text, reactions_count, reply_count, forwards, date, category "
    "FROM messages WHERE is_reply=0"
).fetchall()
conn.close()
id_map = {r[0]: r for r in rows}


def extract_body(t):
    m = re.search(r"---\s*\n(.*?)\n---", t or "", re.DOTALL)
    return (m.group(1).strip() if m else t.strip()[:300]) or ""


def profile(label, idxs, max_sample=3000):
    """Profile a cluster from its point indices."""
    n = len(idxs)
    step = max(1, n // max_sample)
    scores, cats, samples = [], [], []
    for i in idxs[::step]:
        r = id_map.get(int(eids[i]))
        if r:
            scores.append(r[2]*1 + r[3]*2 + r[4]*3)
            cats.append((r[6] or "unknown").lower())
            samples.append(extract_body(r[1]))
    if not samples:
        return
    viral = (np.array(scores) >= np.percentile(scores, 75)).mean()
    top_cats = Counter(cats).most_common(2)
    words = " ".join(samples).lower().split()
    stop = set(
        "the a an is are was were be been to of in for on with at by from "
        "and or but if so as it its i my me we you your he she they this "
        "that do dont does did have has had not no just like get got can "
        "will would could should know think feel really also even still much "
        "many some any all very im ive its dont didnt wont cant isnt wasnt "
        "what when why how who there here up out off over into then than now "
        "one about more way been being hasnt havent doesnt wouldnt couldnt "
        "shouldnt need going go want am are got oh lol haha thats th st nd rd"
        .split()
    )
    word_counts = Counter(w for w in words if w not in stop and len(w) > 3)
    kw = " ".join(w for w, _ in word_counts.most_common(12))
    center = proj[idxs].mean(axis=0)
    best = int(np.argmin(np.linalg.norm(proj[idxs] - center, axis=1)))
    ex = samples[min(best // step, len(samples) - 1)][:130]
    print(
        f"  {label}  n={n:>6}  {n/len(proj)*100:>4.1f}%  viral={viral:.0%}  "
        f"score~{np.mean(scores):.0f}  {top_cats[0][0]}"
    )
    print(f"    kw: {kw}")
    print(f'    eg: "{ex}..."')


from sklearn.cluster import KMeans, MeanShift, estimate_bandwidth
from sklearn.mixture import GaussianMixture
from sklearn.metrics import silhouette_score

# ── 1. KMeans high-K ─────────────────────────────────────────────

print("=== KMEANS ===")
for k in [6, 10, 15, 20, 30]:
    t0 = time.time()
    labels = KMeans(n_clusters=k, random_state=42, n_init=3).fit_predict(proj)
    sil = silhouette_score(proj, labels)
    print(f"\nK={k}  sil={sil:.3f}  ({time.time()-t0:.1f}s)")
    sizes = [(labels == c).sum() for c in range(k)]
    big = np.argsort(sizes)[-8:][::-1]
    for rank, cid in enumerate(big):
        profile(f"  #{rank+1} c{cid}:", np.where(labels == cid)[0])
    print()

# ── 2. Mean Shift (sample → full) ─────────────────────────────────

print("=== MEAN SHIFT ===")
n_sample = min(15000, len(proj))
rng = np.random.RandomState(42)
sample_idx = rng.choice(len(proj), n_sample, replace=False)
t0 = time.time()
bw = estimate_bandwidth(proj[sample_idx], quantile=0.2, n_samples=3000)
print(f"  bandwidth={bw:.3f}  ({time.time()-t0:.1f}s)", flush=True)
ms = MeanShift(bandwidth=bw, bin_seeding=True, n_jobs=1)
labels_s = ms.fit_predict(proj[sample_idx])
n_c = len(set(labels_s) - {-1})
sil_s = silhouette_score(proj[sample_idx], labels_s)
print(f"  sample: {n_c} clusters, sil={sil_s:.3f}  ({time.time()-t0:.1f}s)", flush=True)

# Propagate to full set
from sklearn.neighbors import NearestCentroid
if n_c > 1:
    NearestCentroid().fit(proj[sample_idx], labels_s)
    labels_full = NearestCentroid().predict(proj)
    sil_f = silhouette_score(proj, labels_full)
    print(f"  full: {len(set(labels_full))} clusters, sil={sil_f:.3f}")
    sizes = [(labels_full == c).sum() for c in set(labels_full)]
    big = sorted(
        [c for c in set(labels_full) if c >= 0],
        key=lambda c: -(labels_full == c).sum(),
    )[:10]
    for rank, cid in enumerate(big):
        profile(f"  #{rank+1} c{cid}:", np.where(labels_full == cid)[0])
print()

# ── 3. Gaussian Mixture ────────────────────────────────────────

print("=== GAUSSIAN MIXTURE ===")
for k in [6, 10, 15, 20]:
    t0 = time.time()
    labels = GaussianMixture(n_components=k, random_state=42, n_init=3).fit_predict(proj)
    sil = silhouette_score(proj, labels)
    print(f"\nGMM-{k}  sil={sil:.3f}  ({time.time()-t0:.1f}s)")
    sizes = [(labels == c).sum() for c in range(k)]
    big = np.argsort(sizes)[-8:][::-1]
    for rank, cid in enumerate(big):
        profile(f"  #{rank+1} c{cid}:", np.where(labels == cid)[0])
    print()
