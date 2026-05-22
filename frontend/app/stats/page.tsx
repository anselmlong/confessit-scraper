export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

import { Nav } from '@/components/Nav';
import { getStats, getMonthlyCounts, getLandscape, getInsights } from '@/lib/api';

/* ── Helpers ───────────────────────────────────────── */

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return n.toLocaleString();
}

function OverviewStat({ val, lbl }: { val: string; lbl: string }) {
  return (
    <div className="rounded-lg p-4 text-center border-t-[3px] transition-colors"
         style={{ background: 'var(--surface-alt)', borderColor: 'var(--blue)' }}>
      <div className="text-2xl font-black" style={{ color: 'var(--blue)' }}>{val}</div>
      <div className="text-[0.7rem] uppercase tracking-wide mt-1" style={{ color: 'var(--text-3)' }}>{lbl}</div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl p-5 shadow-sm mb-5" style={{ background: 'var(--surface)' }}>
      <h2 className="text-[0.85rem] font-bold uppercase tracking-[0.8px] mb-4 pb-2 inline-block border-b-2"
          style={{ color: 'var(--blue)', borderColor: 'var(--orange)' }}>
        {title}
      </h2>
      {children}
    </section>
  );
}

function TaxaTable({ regions }: { regions: Record<string, { size_pct: number; keywords: string }> }) {
  const entries = Object.entries(regions);
  const maxPct = Math.max(...entries.map(([, v]) => v.size_pct), 1);
  return (
    <div className="space-y-3 mt-2">
      {entries.map(([key, val]) => (
        <div key={key} className="flex flex-col gap-1">
          <div className="flex items-center justify-between text-[0.83rem]">
            <span className="font-semibold" style={{ color: 'var(--text-1)' }}>
              {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
            </span>
            <span className="font-bold" style={{ color: 'var(--blue)' }}>{val.size_pct}%</span>
          </div>
          <div className="h-[10px] rounded-full overflow-hidden" style={{ background: 'var(--surface-mid)' }}>
            <div className="h-full rounded-full" style={{
              width: `${(val.size_pct / maxPct) * 100}%`,
              background: 'linear-gradient(90deg, var(--blue), var(--blue-mid))',
            }} />
          </div>
          <div className="text-[0.72rem]" style={{ color: 'var(--text-muted)' }}>{val.keywords}</div>
        </div>
      ))}
    </div>
  );
}

function MonthlyBar({ month, count, max }: { month: string; count: number; max: number }) {
  return (
    <div className="flex items-center gap-2.5 text-[0.78rem]">
      <span className="w-14 text-right shrink-0" style={{ color: 'var(--text-3)' }}>{month}</span>
      <div className="h-[22px] rounded-sm min-w-[2px]" style={{
        width: `${(count / max) * 100}%`, background: 'var(--blue)',
      }} />
      <span style={{ color: 'var(--text-3)', minWidth: '2rem' }}>{count}</span>
    </div>
  );
}

function BarRow({ label, value, maxVal, color }: { label: string; value: number | string; maxVal: number; color?: string }) {
  const numVal = typeof value === 'string' ? parseFloat(value) : value;
  const pct = maxVal > 0 ? (numVal / maxVal) * 100 : 0;
  const c = color || 'var(--blue)';
  return (
    <div className="flex items-center gap-2 text-[0.82rem] mb-2">
      <span className="w-36 text-right shrink-0 truncate" style={{ color: 'var(--text-2)' }}>{label}</span>
      <div className="h-[18px] rounded-sm flex-1 min-w-0" style={{ background: 'var(--surface-mid)' }}>
        <div className="h-full rounded-sm flex items-center justify-end px-1.5 text-[0.65rem] font-bold text-white"
             style={{ width: `${Math.min(pct, 100)}%`, background: c }}>
          {pct > 15 ? value : ''}
        </div>
      </div>
      {pct <= 15 && <span className="text-[0.72rem] font-bold shrink-0" style={{ color }}>{value}</span>}
    </div>
  );
}

/* ── Page ───────────────────────────────────────────── */

export default async function StatsPage() {
  const [landscape, stats, monthly, insights] = await Promise.all([
    getLandscape(),
    getStats(),
    getMonthlyCounts(),
    getInsights(),
  ]);

  const regions = landscape?.cluster_taxonomy?.["4_main_regions"];
  const maxMonthly = monthly.length > 0 ? Math.max(...monthly.map(m => m.cnt), 1) : 1;

  // Pre-compute max values for bar charts
  const maxFeatureBoost = insights?.feature_correlations
    ? Math.max(...insights.feature_correlations.map((f: any) => Math.abs(f.boost)), 1) : 1;
  const maxHourScore = insights?.hour_impact
    ? Math.max(...insights.hour_impact.map((h: any) => h.avg_score), 1) : 1;
  const maxDayScore = insights?.day_impact
    ? Math.max(...insights.day_impact.map((d: any) => d.avg_score), 1) : 1;
  const maxCatViral = insights?.category_virality
    ? Math.max(...insights.category_virality.map((c: any) => c.viral_rate), 0.01) : 1;

  return (
    <>
      <Nav activePage="stats" />
      <header className="text-white px-4 md:px-6 py-5 md:py-8" style={{ background: 'linear-gradient(135deg, #003D7C 0%, #00509E 100%)' }}>
        <div className="max-w-5xl mx-auto">
          <h1 className="text-lg md:text-2xl font-bold leading-snug">Channel Statistics &amp; Landscape</h1>
          <p className="text-white/75 mt-1 text-sm">
            Embedding analysis, score distributions, ML topic clusters, and viral insights
          </p>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 md:px-4 pb-12 md:pb-16 pt-4 md:pt-6 space-y-1">
        {stats && (
          <Section title="Overview">
            <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))' }}>
              <OverviewStat val={stats.total.toLocaleString()} lbl="Total Posts" />
              <OverviewStat val={fmt(stats.total_views ?? 0)} lbl="Total Views" />
              <OverviewStat val={String(stats.avg_reactions ?? 0)} lbl="Avg Reactions" />
              <OverviewStat val={String(stats.days_active ?? 0)} lbl="Days Active" />
              <OverviewStat val={String(stats.avg_words ?? 0)} lbl="Avg Words" />
              <OverviewStat val={`${stats.first_date ?? '—'}–${stats.last_date ?? '—'}`} lbl="Date Range" />
            </div>
          </Section>
        )}

        {landscape?.score_distribution && (
          <Section title="Score Distribution">
            <p className="text-[0.88rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
              Engagement follows a <strong>long tail distribution</strong> — most posts score under 50,
              while a tiny fraction of viral content captures the bulk of attention.
            </p>
            <img src="/blog/score_distribution.png" alt="Score distribution" className="w-full rounded-lg mb-3" style={{ background: 'var(--surface)' }} />
            <div className="flex flex-wrap gap-4 text-[0.88rem]">
              {['mean','median','p75','p90','max'].map(k => (
                <div key={k} className="flex flex-col items-center min-w-[80px]">
                  <span className="text-xl font-black" style={{ color: 'var(--blue)' }}>
                    {landscape.score_distribution[k as keyof typeof landscape.score_distribution]}
                  </span>
                  <span className="text-[0.7rem] uppercase tracking-wide mt-0.5" style={{ color: 'var(--text-3)' }}>{k}</span>
                </div>
              ))}
            </div>
          </Section>
        )}

        {landscape?.categories && (
          <Section title="Category Breakdown">
            <p className="text-[0.88rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
              Categories extracted from confession title text — <strong>91% of posts</strong> have a hashtag prefix
              like <code>#studies</code>, <code>#romance</code>, or <code>#campus</code>.
            </p>
            <img src="/blog/category_breakdown.png" alt="Category breakdown" className="w-full rounded-lg mb-3" style={{ background: 'var(--surface)' }} />
          </Section>
        )}

        {regions && (
          <Section title="Topic Regions (ML Clusters)">
            <p className="text-[0.88rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
              Using Mean Shift + HDBSCAN clustering on embeddings to discover <em>four</em> natural topic regions.
            </p>
            <TaxaTable regions={regions} />
            <div className="text-[0.75rem] mt-1" style={{ color: 'var(--text-muted)' }}>
              Method: {landscape?.cluster_taxonomy.method}
            </div>
          </Section>
        )}

        {landscape?.cluster_taxonomy && (
          <Section title="Embedding Landscape">
            <p className="text-[0.88rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
              UMAP projection of all 72K confessions — a <strong>continuous gradient</strong> with
              viral posts concentrated in specific regions.
            </p>
            <img src="/blog/umap_landscape.png" alt="UMAP landscape" className="w-full rounded-lg mb-3" style={{ background: 'var(--surface)' }} />
          </Section>
        )}

        {landscape && (
          <Section title="Viral Insights">
            <p className="text-[0.88rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
              Posts above <strong style={{ color: 'var(--orange)' }}>{landscape.viral_threshold}</strong> are
              viral (top {(landscape.viral_rate * 100).toFixed(0)}%).
            </p>
            <img src="/blog/viral_by_category.png" alt="Viral by topic" className="w-full rounded-lg mb-3" style={{ background: 'var(--surface)' }} />
            <div className="rounded-lg p-4 text-[0.88rem] leading-relaxed border-l-4 border-[var(--orange)]"
                 style={{ background: 'var(--surface-alt)' }}>
              <strong style={{ color: 'var(--orange)' }}>Key finding:</strong>{' '}
              Dating posts form the only consistent viral pocket — ~70% of viral posts come from the dating region.
            </div>
          </Section>
        )}

        {insights && (
          <Section title="Feature Importance: What Drives Scores">
            <p className="text-[0.88rem] leading-relaxed mb-4" style={{ color: 'var(--text-2)' }}>
              Correlation and boost of each feature against engagement score.
              <strong> Baseline avg score: {insights.baseline_avg_score}</strong>.
            </p>
            {insights.feature_correlations.map((f: any) => {
              const absBoost = Math.abs(f.boost);
              const pct = maxFeatureBoost > 0 ? (absBoost / maxFeatureBoost) * 100 : 0;
              const isPositive = f.boost >= 0;
              const barColor = isPositive ? 'var(--blue)' : 'var(--orange)';
              const pctColor = isPositive ? 'var(--blue)' : 'var(--orange)';
              return (
                <div key={f.feature} className="flex items-center gap-2 text-[0.82rem] mb-2.5">
                  <span className="w-36 text-right shrink-0 truncate font-medium" style={{ color: 'var(--text-1)' }}>
                    {f.feature}
                  </span>
                  <div className="h-[18px] rounded-sm flex-1 min-w-0" style={{ background: 'var(--surface-mid)' }}>
                    <div className="h-full rounded-sm flex items-center px-1.5 text-[0.65rem] font-bold text-white"
                         style={{ width: `${Math.min(pct, 100)}%`, background: barColor }}>
                      {pct > 12 ? `${isPositive ? '+' : ''}${f.boost}` : ''}
                    </div>
                  </div>
                  <span className="text-[0.68rem] w-14 shrink-0" style={{ color: 'var(--text-muted)' }}>
                    r={f.correlation}
                  </span>
                  {pct <= 12 && (
                    <span className="text-[0.72rem] font-bold shrink-0" style={{ color: pctColor }}>
                      {isPositive ? '+' : ''}{f.boost}
                    </span>
                  )}
                  {f.has_pct !== undefined && (
                    <span className="text-[0.68rem] w-14 shrink-0" style={{ color: 'var(--text-muted)' }}>
                      {f.has_pct}% use it
                    </span>
                  )}
                </div>
              );
            })}
          </Section>
        )}

        {insights && (
          <Section title="Best Time to Post">
            <p className="text-[0.88rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
              Average score by time of day and day of week.
            </p>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <h3 className="text-[0.75rem] uppercase tracking-wide font-semibold mb-2" style={{ color: 'var(--text-3)' }}>
                  Hour of Day
                </h3>
                {insights.hour_impact.map((h: any) => (
                  <BarRow key={h.label} label={h.label} value={h.avg_score} maxVal={maxHourScore} />
                ))}
              </div>
              <div>
                <h3 className="text-[0.75rem] uppercase tracking-wide font-semibold mb-2" style={{ color: 'var(--text-3)' }}>
                  Day of Week
                </h3>
                {insights.day_impact.map((d: any) => (
                  <BarRow key={d.day} label={d.day} value={d.avg_score} maxVal={maxDayScore} />
                ))}
              </div>
            </div>
          </Section>
        )}

        {insights?.category_virality && (
          <Section title="Category Viral Rates">
            <p className="text-[0.88rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
              Which categories go viral most often. <strong>Viral rate</strong> = % of posts in that category
              in the top 25% by score.
            </p>
            <div className="space-y-2">
              {insights.category_virality.map((c: any) => (
                <div key={c.category} className="flex items-center gap-2 text-[0.82rem]">
                  <span className="w-36 text-right shrink-0 truncate font-medium" style={{ color: 'var(--text-1)' }}>
                    {c.category}
                  </span>
                  <div className="h-[18px] rounded-sm flex-1 min-w-0" style={{ background: 'var(--surface-mid)' }}>
                    <div className="h-full rounded-sm flex items-center px-1.5 text-[0.65rem] font-bold text-white"
                         style={{ width: `${(c.viral_rate / maxCatViral) * 100}%`, background: 'var(--orange)' }}>
                      {(c.viral_rate / maxCatViral) > 0.15 ? `${(c.viral_rate * 100).toFixed(0)}%` : ''}
                    </div>
                  </div>
                  <span className="text-[0.68rem] w-14 shrink-0" style={{ color: 'var(--text-muted)' }}>
                    {(c.viral_rate / maxCatViral) <= 0.15 ? `${(c.viral_rate * 100).toFixed(0)}%` : ''}
                  </span>
                  <span className="text-[0.68rem] shrink-0" style={{ color: 'var(--text-muted)' }}>
                    avg {c.avg_score} · n={c.post_count}
                  </span>
                </div>
              ))}
            </div>
          </Section>
        )}

        {insights?.length_impact && (
          <Section title="Post Length vs Engagement">
            <p className="text-[0.88rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
              Longer posts perform significantly better — <strong>long posts (&gt;80 words) average
              {insights.length_impact.find((l: any) => l.label === 'long')?.avg_score ?? ''}</strong>,
              nearly double the medium post average.
            </p>
            <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))' }}>
              {insights.length_impact.map((l: any) => (
                <div key={l.label} className="rounded-lg p-3 text-center border-t-[3px]"
                     style={{ background: 'var(--surface-alt)', borderColor: l.label === 'long' ? 'var(--orange)' : 'var(--blue)' }}>
                  <div className="text-xl font-black" style={{ color: l.label === 'long' ? 'var(--orange)' : 'var(--blue)' }}>
                    {l.avg_score}
                  </div>
                  <div className="text-[0.65rem] uppercase tracking-wide mt-0.5"
                       style={{ color: 'var(--text-3)' }}>{l.label}</div>
                  <div className="text-[0.68rem] mt-1" style={{ color: 'var(--text-muted)' }}>
                    {((l.post_count / (insights.baseline_avg_score ? stats?.total || 1 : 1)) * 100).toFixed(0)}% of posts
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {landscape?.top_posts?.length > 0 && (
          <Section title="Top 10 Most Engaged Posts">
            <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
              {landscape.top_posts.map((post: any, i: number) => (
                <a key={post.id} href={`/post/${post.id}`}
                   className="flex items-start gap-3 px-1 py-2.5 no-underline transition-colors rounded-lg hover:-translate-y-px"
                   style={{ color: 'var(--text-1)' }}>
                  <span className="text-[0.7rem] font-black w-5 text-right shrink-0 mt-0.5"
                        style={{ color: i < 3 ? 'var(--orange)' : 'var(--text-muted)' }}>#{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-[0.83rem] leading-snug line-clamp-2">{post.excerpt}</div>
                    <div className="text-[0.7rem] mt-1 font-semibold" style={{ color: 'var(--blue)' }}>
                      Score: {post.score.toLocaleString()}
                    </div>
                  </div>
                  <span className="text-[0.7rem] shrink-0 mt-0.5" style={{ color: 'var(--text-muted)' }}>#{post.id}</span>
                </a>
              ))}
            </div>
          </Section>
        )}

        {monthly.length > 0 && (
          <Section title="Monthly Activity">
            <img src="/blog/monthly_activity.png" alt="Monthly activity" className="w-full rounded-lg mb-3" style={{ background: 'var(--surface)' }} />
            <div className="space-y-2">
              {monthly.map(m => (<MonthlyBar key={m.month} month={m.month} count={m.cnt} max={maxMonthly} />))}
            </div>
          </Section>
        )}

        <Section title="Methodology">
          <div className="space-y-2 text-[0.88rem] leading-relaxed" style={{ color: 'var(--text-2)' }}>
            <p><strong>Embedding:</strong> text-embedding-3-small (512d).</p>
            <p><strong>Reduction:</strong> UMAP (15 neighbours, min distance 0.1).</p>
            <p><strong>Clustering:</strong> Mean Shift (bandwidth=2.14) + HDBSCAN.</p>
            <p><strong>Virality:</strong> Score = reactions + 2× replies + 3× forwards. Top 25% = viral.</p>
            <p><strong>Feature impact:</strong> Per-post features computed from text (emoji count, curse words, relationship keywords, etc.). Correlation measured against engagement score across all 72K posts.</p>
            <p><strong>Source:</strong> t.me/NUSConfessIT via Telegram API. May 2026.</p>
          </div>
        </Section>
      </main>
    </>
  );
}