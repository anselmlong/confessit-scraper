export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

import { Nav } from '@/components/Nav';
import { getStats, getMonthlyCounts } from '@/lib/db';

/* ── Types ─────────────────────────────────────────── */

interface ScoreDist {
  mean: number; median: number; p75: number; p90: number; max: number;
}

interface RegionInfo {
  size_pct: number; keywords: string;
}

interface LandscapeData {
  total_posts: number;
  viral_threshold: number;
  viral_rate: number;
  categories: Record<string, number>;
  score_distribution: ScoreDist;
  top_posts: { id: number; score: number; excerpt: string }[];
  cluster_taxonomy: {
    "4_main_regions": Record<string, RegionInfo>;
    method: string;
    embedding_model: string;
  };
}

/* ── Helpers ───────────────────────────────────────── */

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return n.toLocaleString();
}

function pctLabel(n: number): string {
  return `${(n * 100).toFixed(0)}%`;
}

/* ── API fetch with fallback ───────────────────────── */

async function fetchLandscape(): Promise<LandscapeData | null> {
  const apiBase = process.env.NEXT_PUBLIC_VPS_API;
  if (apiBase) {
    try {
      const res = await fetch(`${apiBase}/api/landscape`, { next: { revalidate: 300 } });
      if (res.ok) return res.json();
    } catch {
      // fall through to local SQLite
    }
  }
  return null;
}

async function fetchStats() {
  const apiBase = process.env.NEXT_PUBLIC_VPS_API;
  if (apiBase) {
    try {
      const res = await fetch(`${apiBase}/api/stats`, { next: { revalidate: 300 } });
      if (res.ok) return res.json();
    } catch {
      // fall through
    }
  }
  return null;
}

async function fetchMonthly() {
  const apiBase = process.env.NEXT_PUBLIC_VPS_API;
  if (apiBase) {
    try {
      const res = await fetch(`${apiBase}/api/monthly`, { next: { revalidate: 300 } });
      if (res.ok) return res.json();
    } catch {
      // fall through
    }
  }
  return null;
}

/* ── Components ────────────────────────────────────── */

function OverviewStat({ val, lbl }: { val: string; lbl: string }) {
  return (
    <div
      className="rounded-lg p-4 text-center border-t-[3px] transition-colors"
      style={{ background: 'var(--surface-alt)', borderColor: 'var(--blue)' }}
    >
      <div className="text-2xl font-black break-words" style={{ color: 'var(--blue)' }}>
        {val}
      </div>
      <div className="text-[0.7rem] uppercase tracking-wide mt-1" style={{ color: 'var(--text-3)' }}>
        {lbl}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl p-5 shadow-sm mb-5" style={{ background: 'var(--surface)' }}>
      <h2
        className="text-[0.85rem] font-bold uppercase tracking-[0.8px] mb-4 pb-2 inline-block border-b-2"
        style={{ color: 'var(--blue)', borderColor: 'var(--orange)' }}
      >
        {title}
      </h2>
      {children}
    </section>
  );
}

function TaxaTable({ regions }: { regions: Record<string, RegionInfo> }) {
  const entries = Object.entries(regions);
  const maxPct = Math.max(...entries.map(([, v]) => v.size_pct), 1);
  return (
    <div className="space-y-3 mt-2">
      {entries.map(([key, val]) => {
        const label = key
          .replace(/_/g, ' ')
          .replace(/\b\w/g, c => c.toUpperCase());
        return (
          <div key={key} className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-[0.83rem]">
              <span className="font-semibold" style={{ color: 'var(--text-1)' }}>{label}</span>
              <span className="font-bold" style={{ color: 'var(--blue)' }}>{val.size_pct}%</span>
            </div>
            <div className="h-[10px] rounded-full overflow-hidden" style={{ background: 'var(--surface-mid)' }}>
              <div
                className="h-full rounded-full"
                style={{
                  width: `${(val.size_pct / maxPct) * 100}%`,
                  background: 'linear-gradient(90deg, var(--blue), var(--blue-mid))',
                }}
              />
            </div>
            <div className="text-[0.72rem]" style={{ color: 'var(--text-muted)' }}>
              {val.keywords}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function TopPostRow({ post, rank }: { post: { id: number; score: number; excerpt: string }; rank: number }) {
  return (
    <a
      href={`/post/${post.id}`}
      className="flex items-start gap-3 px-1 py-2.5 no-underline transition-colors rounded-lg hover:-translate-y-px"
      style={{ color: 'var(--text-1)', textDecoration: 'none' }}
    >
      <span
        className="text-[0.7rem] font-black w-5 text-right shrink-0 mt-0.5"
        style={{ color: rank <= 3 ? 'var(--orange)' : 'var(--text-muted)' }}
      >
        #{rank}
      </span>
      <div className="flex-1 min-w-0">
        <div className="text-[0.83rem] leading-snug line-clamp-2">{post.excerpt}</div>
        <div className="text-[0.7rem] mt-1 font-semibold" style={{ color: 'var(--blue)' }}>
          Score: {post.score.toLocaleString()}
        </div>
      </div>
      <span className="text-[0.7rem] shrink-0 mt-0.5" style={{ color: 'var(--text-muted)' }}>
        #{post.id}
      </span>
    </a>
  );
}

function MonthlyBar({ month, count, max }: { month: string; count: number; max: number }) {
  return (
    <div className="flex items-center gap-2.5 text-[0.78rem]">
      <span className="w-14 text-right shrink-0" style={{ color: 'var(--text-3)' }}>
        {month}
      </span>
      <div
        className="h-[22px] rounded-sm min-w-[2px]"
        style={{
          width: `${(count / max) * 100}%`,
          background: 'var(--blue)',
        }}
      />
      <span style={{ color: 'var(--text-3)', minWidth: '2rem' }}>{count}</span>
    </div>
  );
}

/* ── Main Page ─────────────────────────────────────── */

export default async function StatsPage() {
  // Try API first, fall back to local SQLite
  const [landscape, apiStats, apiMonthly] = await Promise.all([
    fetchLandscape(),
    fetchStats(),
    fetchMonthly(),
  ]);

  // Local fallback for stats
  const localStats = (() => {
    try { return getStats(); } catch { return null; }
  })();

  // Local fallback for monthly
  const localMonthly = (() => {
    try { return getMonthlyCounts(); } catch { return []; }
  })();

  // Merge: prefer API, fall back to SQLite
  const stats = apiStats ?? (localStats ? {
    total: localStats.total,
    total_replies: localStats.total_replies,
    first_date: localStats.first_date,
    last_date: localStats.last_date,
    days_active: localStats.days_active,
    total_views: localStats.total_views,
    avg_reactions: localStats.avg_reactions,
    avg_words: localStats.avg_words,
    max_reactions: localStats.max_reactions,
    total_posts: localStats.total,
  } : null);

  const monthly = apiMonthly ?? localMonthly.map(m => ({
    month: m.month,
    count: m.cnt,
  }));

  const maxMonthly = monthly.length > 0 ? Math.max(...monthly.map((m: { count: number }) => m.count), 1) : 1;

  // ML-derived regions from the embedding analysis, not raw categories
  const regions = landscape?.cluster_taxonomy?.["4_main_regions"];
  const regionsList = regions ? Object.entries(regions) : [];
  const totalRegionPct = regionsList.reduce((a, [, v]) => a + v.size_pct, 0);

  return (
    <>
      <Nav activePage="stats" />

      {/* Hero header */}
      <header
        className="text-white px-6 py-8"
        style={{ background: 'linear-gradient(135deg, #003D7C 0%, #00509E 100%)' }}
      >
        <div className="max-w-5xl mx-auto">
          <h1 className="text-2xl font-bold">Channel Statistics &amp; Landscape</h1>
          <p className="text-white/75 mt-1.5 text-sm">
            Embedding analysis, score distributions, ML-derived topic clusters, and viral insights
          </p>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 pb-16 pt-6 space-y-1">

        {/* ── 1. Overview ──────────────────────────────── */}
        {stats && (
          <Section title="Overview">
            <div
              className="grid gap-3"
              style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))' }}
            >
              <OverviewStat val={stats.total_posts?.toLocaleString() ?? String(stats.total)} lbl="Total Posts" />
              <OverviewStat val={fmt(stats.total_replies ?? 0)} lbl="Total Replies" />
              <OverviewStat val={fmt(stats.total_views ?? 0)} lbl="Total Views" />
              <OverviewStat val={String(stats.avg_reactions ?? 0)} lbl="Avg Reactions" />
              <OverviewStat val={String(stats.days_active ?? 0)} lbl="Days Active" />
              <OverviewStat val={String(stats.avg_words ?? 0)} lbl="Avg Words" />
              <OverviewStat val={`${stats.first_date ?? '—'}–${stats.last_date ?? '—'}`} lbl="Date Range" />
            </div>
          </Section>
        )}

        {/* ── 2. Score Distribution ──────────────────── */}
        {landscape?.score_distribution && (
          <Section title="Score Distribution">
            <p className="text-[0.88rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
              Engagement follows a <strong>long tail distribution</strong> — most posts score under 50,
              while a tiny fraction of viral content captures the bulk of attention.
            </p>
            <img src="/blog/score_distribution.png" alt="Score distribution histogram" className="w-full rounded-lg mb-3" style={{ background: 'var(--surface)' }} />
            <div className="space-y-3">
              <div className="flex flex-wrap gap-4 text-[0.88rem]">
                {[
                  { lbl: 'Mean', val: landscape.score_distribution.mean, pct: false },
                  { lbl: 'Median', val: landscape.score_distribution.median, pct: false },
                  { lbl: 'P75', val: landscape.score_distribution.p75, pct: false },
                  { lbl: 'P90', val: landscape.score_distribution.p90, pct: false },
                  { lbl: 'Max', val: landscape.score_distribution.max, pct: false },
                ].map(({ lbl, val }) => (
                  <div key={lbl} className="flex flex-col items-center min-w-[80px]">
                    <span className="text-xl font-black" style={{ color: 'var(--blue)' }}>{val}</span>
                    <span className="text-[0.7rem] uppercase tracking-wide mt-0.5" style={{ color: 'var(--text-3)' }}>{lbl}</span>
                  </div>
                ))}
              </div>

              {/* Visual distribution bar */}
              <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
                <div className="text-[0.75rem] mb-2 font-semibold" style={{ color: 'var(--text-3)' }}>
                  Percentile Bar (0 → Max)
                </div>
                <div className="h-[14px] rounded-full overflow-hidden relative flex" style={{ background: 'var(--surface-mid)' }}>
                  {[
                    { label: '50%', at: landscape.score_distribution.median / landscape.score_distribution.max },
                    { label: '75%', at: landscape.score_distribution.p75 / landscape.score_distribution.max },
                    { label: '90%', at: landscape.score_distribution.p90 / landscape.score_distribution.max },
                  ].map(({ label, at }) => (
                    <div
                      key={label}
                      className="absolute top-0 bottom-0 w-[2px] z-10"
                      style={{
                        left: `${at * 100}%`,
                        background: 'var(--orange)',
                      }}
                      title={`${label}: ${at.toFixed(2)}`}
                    />
                  ))}
                  <div
                    className="h-full rounded-l-full"
                    style={{
                      width: `${(landscape.score_distribution.median / landscape.score_distribution.max) * 100}%`,
                      background: 'var(--blue)',
                    }}
                  />
                  <div
                    className="h-full"
                    style={{
                      width: `${((landscape.score_distribution.p75 - landscape.score_distribution.median) / landscape.score_distribution.max) * 100}%`,
                      background: 'var(--blue-mid)',
                      opacity: 0.7,
                    }}
                  />
                </div>
                <div className="flex justify-between text-[0.65rem] mt-1" style={{ color: 'var(--text-muted)' }}>
                  <span>0</span>
                  <span>Median {landscape.score_distribution.median}</span>
                  <span>P75 {landscape.score_distribution.p75}</span>
                  <span>Max {landscape.score_distribution.max}</span>
                </div>
              </div>
            </div>
          </Section>
        )}

        {/* ── 2.5 Category Breakdown (Text-Extracted) ── */}
        {landscape?.categories && (
          <Section title="Category Breakdown">
            <p className="text-[0.88rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
              Rather than relying on the database category field (78% null), we extract categories directly from
              the confession title text — <strong>91% of posts have a hashtag prefix</strong> like
              <code> #studies</code>, <code> #romance</code>, or <code> #campus</code>.
            </p>
            <img src="/blog/category_breakdown.png" alt="Category breakdown chart" className="w-full rounded-lg mb-3" style={{ background: 'var(--surface)' }} />
          </Section>
        )}

        {/* ── 3. ML-Derived Topic Regions ──────────────── */}
        {regions && (
          <Section title="Topic Regions (ML Clusters)">
            <p className="text-[0.88rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
              Posts were embedded with <strong>{landscape?.cluster_taxonomy.embedding_model}</strong> and reduced
              via UMAP. Instead of relying on user-applied tags (78% of posts are uncategorised), we used
              <strong> Mean Shift + HDBSCAN</strong> clustering on the embeddings to discover <em>four</em> natural
              topic regions that emerge from the content itself.
            </p>
            <TaxaTable regions={regions} />
            <div className="text-[0.75rem] mt-1" style={{ color: 'var(--text-muted)' }}>
              Method: {landscape?.cluster_taxonomy.method}
            </div>
          </Section>
        )}

        {/* ── 4. Embedding Landscape ───────────────────── */}
        {landscape?.cluster_taxonomy && (
          <Section title="Embedding Landscape">
            <p className="text-[0.88rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
              The UMAP projection of all 72K confessions reveals a <strong>continuous gradient</strong> —
              topics blend into one another with no hard boundaries. Viral posts (orange, right plot) 
              concentrate in specific regions rather than being uniformly distributed.
            </p>
            <img src="/blog/umap_landscape.png" alt="UMAP embedding landscape" className="w-full rounded-lg mb-3" style={{ background: 'var(--surface)' }} />
            <div className="text-[0.75rem]" style={{ color: 'var(--text-muted)' }}>
              Method: {landscape.cluster_taxonomy.method}
            </div>
          </Section>
        )}

        {/* ── 5. Viral Insights ────────────────────────── */}
        {landscape && (
          <Section title="Viral Insights">
            <p className="text-[0.88rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
              Posts with a composite score above{' '}
              <strong style={{ color: 'var(--orange)' }}>{landscape.viral_threshold}</strong> are
              classified as <strong>viral</strong> (top {pctLabel(landscape.viral_rate)} of all posts).
            </p>
            <img src="/blog/viral_by_category.png" alt="Viral rate by topic region" className="w-full rounded-lg mb-3" style={{ background: 'var(--surface)' }} />
            <div
              className="rounded-lg p-4 text-[0.88rem] leading-relaxed"
              style={{ background: 'var(--surface-alt)', borderLeft: '4px solid var(--orange)' }}
            >
              <strong style={{ color: 'var(--orange)' }}>Key finding:</strong>{' '}
              Dating &amp; relationship posts form the <strong>only consistent viral pocket</strong> —
              ~70% of viral posts come from the dating region, versus a ~25% baseline across all other
              regions. This suggests romantic content drives the highest engagement on NUSConfessIT.
            </div>
          </Section>
        )}

        {/* ── 6. Top 10 Most Engaged Posts ──────────────── */}
        {landscape?.top_posts && landscape.top_posts.length > 0 && (
          <Section title="Top 10 Most Engaged Posts">
            <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
              {landscape.top_posts.map((post, i) => (
                <TopPostRow key={post.id} post={post} rank={i + 1} />
              ))}
            </div>
          </Section>
        )}

        {/* ── 7. Monthly Activity ────────────────────────── */}
        {monthly.length > 0 && (
          <Section title="Monthly Activity">
            <p className="text-[0.88rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
              The channel has sustained <strong>3,000+ posts per month</strong> since late 2024 — 
              unusually long-lived for an anonymous confession platform.
            </p>
            <img src="/blog/monthly_activity.png" alt="Monthly activity bar chart" className="w-full rounded-lg mb-3" style={{ background: 'var(--surface)' }} />
            <div className="space-y-2">
              {monthly.map((m: { month: string; count: number }) => (
                <MonthlyBar key={m.month} month={m.month} count={m.count} max={maxMonthly} />
              ))}
            </div>
          </Section>
        )}

        {/* ── 8. Methodology ────────────────────────────── */}
        {landscape?.cluster_taxonomy && (
          <Section title="Methodology">
            <div className="space-y-2 text-[0.88rem] leading-relaxed" style={{ color: 'var(--text-2)' }}>
              <p><strong>Embedding:</strong> Each confession encoded with <code>text-embedding-3-small</code> (512 dimensions).</p>
              <p><strong>Dimensionality Reduction:</strong> UMAP (15 neighbours, min distance 0.1) fit on 15K sample, transformed across all 72K posts.</p>
              <p><strong>Clustering:</strong> Mean Shift (bandwidth=2.14) for region detection, validated against HDBSCAN. Four stable regions identified.</p>
              <p><strong>Virality:</strong> Composite score = reactions + 2× replies + 3× forwards. Top 25% scored posts classified as viral.</p>
              <p><strong>Data Source:</strong> Telegram API via t.me/NUSConfessIT. Analysis date: May 2026.</p>
            </div>
          </Section>
        )}

      </main>
    </>
  );
}