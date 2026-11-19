import Link from 'next/link';
import { Nav } from '@/components/Nav';
import { TimelineExplorer } from '@/components/charts/TimelineExplorer';
import { ShareRows } from '@/components/charts/ShareRows';
import { getStats, getLandscape, getInsights, getCopypastas, getTimeline, getTermTrends, getCategoryTrends } from '@/lib/api';
import { formatShortDate } from '@/lib/date';
import type { TimelineSpan } from '@/lib/types';

const SPANS: { key: TimelineSpan; label: string }[] = [
  { key: '30d', label: '30 days' },
  { key: '90d', label: '90 days' },
  { key: '1y', label: '1 year' },
  { key: 'all', label: 'All time' },
];
const DEFAULT_TERMS = ['exam', 'chatgpt', 'crush'];
const TERM_IDEAS = ['exam, recess', 'chatgpt', 'crush, situationship', 'hall, rc', 'internship, job', 'tinder, hinge'];

function statsHref(span: TimelineSpan, terms: string) {
  const p = new URLSearchParams();
  if (span !== 'all') p.set('span', span);
  if (terms) p.set('terms', terms);
  const q = p.toString();
  return `/stats${q ? `?${q}` : ''}#activity`;
}

/* ── Helpers ───────────────────────────────────────── */

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return n.toLocaleString();
}

function OverviewStat({ val, lbl }: { val: string; lbl: string }) {
  return (
    <div className="px-4 py-3.5 md:px-5 md:py-4 border-[var(--border)] max-sm:[&:nth-child(odd)]:border-r max-sm:[&:nth-child(n+3)]:border-t sm:[&:not(:first-child)]:border-l max-sm:[&:nth-child(5)]:col-span-2">
      <div className="text-[0.74rem]" style={{ color: 'var(--text-muted)' }}>{lbl}</div>
      <div className="text-xl md:text-2xl font-semibold tracking-[-0.03em] tabular-nums mt-0.5" style={{ color: 'var(--text-1)' }}>{val}</div>
    </div>
  );
}

function Section({ id, title, desc, actions, children }: {
  id?: string; title: string; desc?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <section id={id} className="panel p-5 md:p-6 mb-5 scroll-mt-20">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 mb-4">
        <div className="min-w-0 max-w-2xl">
          <h2 className="text-[1.05rem] font-semibold tracking-[-0.02em] m-0" style={{ color: 'var(--text-1)' }}>{title}</h2>
          {desc && <p className="text-[0.86rem] leading-relaxed mt-1 mb-0" style={{ color: 'var(--text-3)' }}>{desc}</p>}
        </div>
        {actions}
      </div>
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

function BarRow({ label, value, maxVal, color }: { label: string; value: number | string; maxVal: number; color?: string }) {
  const numVal = typeof value === 'string' ? parseFloat(value) : value;
  const pct = maxVal > 0 ? (numVal / maxVal) * 100 : 0;
  const c = color || 'var(--fill)';
  return (
    <div className="flex items-center gap-2 text-[0.82rem] mb-2">
      <span className="w-14 sm:w-36 text-right shrink-0 truncate" style={{ color: 'var(--text-2)' }}>{label}</span>
      <div className="h-[18px] rounded-sm flex-1 min-w-0" style={{ background: 'var(--surface-mid)' }}>
        <div className="h-full rounded-sm flex items-center justify-end px-1.5 text-[0.68rem] font-bold tabular-nums"
             style={{ width: `${Math.min(pct, 100)}%`, background: c, color: 'var(--on-fill)' }}>
          {pct > 15 ? value : ''}
        </div>
      </div>
      {pct <= 15 && <span className="text-[0.72rem] font-bold shrink-0 tabular-nums" style={{ color: color || 'var(--blue)' }}>{value}</span>}
    </div>
  );
}

/* ── Page ───────────────────────────────────────────── */

export default async function StatsPage({
  searchParams,
}: {
  searchParams: Promise<{ span?: string; terms?: string }>;
}) {
  const sp = await searchParams;
  const span: TimelineSpan = SPANS.some(s => s.key === sp.span) ? (sp.span as TimelineSpan) : 'all';
  const termsRaw = (sp.terms ?? '').trim();
  const terms = (termsRaw ? termsRaw.split(',') : DEFAULT_TERMS).map(t => t.trim().toLowerCase()).filter(Boolean).slice(0, 4);

  const [landscape, stats, insights, copypasta, timeline, termTrends, categoryTrends] = await Promise.all([
    getLandscape(),
    getStats(),
    getInsights(),
    getCopypastas(),
    getTimeline(span),
    getTermTrends(terms),
    getCategoryTrends(),
  ]);

  const regions = landscape?.cluster_taxonomy?.["4_main_regions"];
  const months = categoryTrends[0]?.series.map(p => p.month) ?? termTrends[0]?.series.map(p => p.month) ?? [];

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

      <main className="max-w-5xl mx-auto px-4 pb-12 md:pb-16">
        <header className="pt-4 pb-6 md:pt-8 md:pb-8">
          <h1 className="text-[1.75rem] md:text-[2.25rem] font-semibold tracking-[-0.035em] leading-tight m-0" style={{ color: 'var(--text-1)' }}>
            Trends &amp; stats
          </h1>
          <p className="text-[0.95rem] mt-2 mb-0 max-w-2xl" style={{ color: 'var(--text-3)' }}>
            What NUS has been confessing, week by week
            {stats && <> since {formatShortDate(stats.first_date)}. Updated hourly from the channel.</>}
          </p>
        </header>

        {stats && (
          <div className="panel grid grid-cols-2 sm:grid-cols-5 mb-5 overflow-hidden">
            <OverviewStat val={stats.total.toLocaleString()} lbl="Confessions" />
            <OverviewStat val={fmt(stats.total_views ?? 0)} lbl="Views" />
            <OverviewStat val={String(stats.avg_reactions ?? 0)} lbl="Avg reactions" />
            <OverviewStat val={String(stats.avg_words ?? 0)} lbl="Avg words" />
            <OverviewStat val={(stats.days_active ?? 0).toLocaleString()} lbl="Days tracked" />
          </div>
        )}

        <Section
          id="activity"
          title="Activity over time"
          desc="How much gets posted, and how hard it lands. Pins mark busy stretches and the posts everyone was talking about."
          actions={
            <nav aria-label="Time window" className="inline-flex p-0.5 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-alt)' }}>
              {SPANS.map(s => (
                <Link key={s.key} href={statsHref(s.key, termsRaw)} scroll={false} aria-current={span === s.key ? 'true' : undefined}
                      className="px-3 py-1 pointer-coarse:py-2 rounded-md text-[0.8rem] font-medium no-underline whitespace-nowrap transition-colors"
                      style={span === s.key
                        ? { background: 'var(--surface)', color: 'var(--text-1)', boxShadow: 'var(--shadow-1), 0 0 0 1px var(--border)' }
                        : { color: 'var(--text-3)' }}>
                  {s.label}
                </Link>
              ))}
            </nav>
          }
        >
          {timeline
            ? <TimelineExplorer key={span} data={timeline} />
            : <p className="text-[0.88rem] py-8 text-center" style={{ color: 'var(--text-muted)' }}>The timeline is unavailable right now. Try again in a minute.</p>}
        </Section>

        <Section
          id="words"
          title="Word trends"
          desc={<>Share of each month&rsquo;s confessions that mention a word. Compare up to four, separated by commas. Each row is scaled to its own peak.</>}
        >
          <form action="/stats" method="get" className="flex flex-wrap gap-2 mb-3">
            {span !== 'all' && <input type="hidden" name="span" value={span} />}
            <label htmlFor="terms" className="sr-only">Words to compare</label>
            <input
              id="terms" name="terms" defaultValue={terms.join(', ')} placeholder="exam, crush, chatgpt"
              className="search-input flex-1 min-w-[14rem] px-3 py-2 pointer-coarse:min-h-11 rounded-lg text-[0.9rem] border font-[inherit]"
              style={{ background: 'var(--surface)', color: 'var(--text-1)', borderColor: 'var(--border)' }}
            />
            <button type="submit" className="px-4 py-2 pointer-coarse:min-h-11 rounded-lg font-medium text-[0.86rem] border-none cursor-pointer"
                    style={{ background: 'var(--ink)', color: 'var(--on-ink)' }}>
              Compare
            </button>
          </form>
          <div className="flex flex-wrap items-center gap-1.5 mb-5 text-[0.76rem]" style={{ color: 'var(--text-muted)' }}>
            <span className="mr-1">Try</span>
            {TERM_IDEAS.map(t => (
              <Link key={t} href={`${statsHref(span, t.replace(/\s/g, ''))}`.replace('#activity', '#words')} scroll={false}
                    className="px-2 py-0.5 pointer-coarse:py-1.5 rounded-md border no-underline transition-colors hover:text-[var(--text-1)] hover:border-[var(--text-muted)]"
                    style={{ borderColor: 'var(--border)', color: 'var(--text-2)' }}>
                {t}
              </Link>
            ))}
          </div>
          <ShareRows
            rows={termTrends.map(t => ({ label: t.term, total: t.total, series: t.series, peak: t.peak }))}
            months={months}
            linkTerms
            emptyNote="Word trends are unavailable right now."
          />
        </Section>

        {categoryTrends.length > 0 && (
          <Section
            id="categories"
            title="Category mix"
            desc="Share of each month’s confessions by the hashtag they were filed under. Each row is scaled to its own range, so a small category’s swings look as large as a big one’s."
          >
            <ShareRows
              rows={categoryTrends.map(c => ({
                label: c.category,
                total: c.total,
                series: c.series,
                summary: `${Math.round((c.total / Math.max(categoryTrends.reduce((n, x) => n + x.total, 0), 1)) * 1000) / 10}% of all posts`,
              }))}
              months={months}
            />
          </Section>
        )}

        <h2 className="text-[0.95rem] font-semibold tracking-[-0.01em] mt-10 mb-3 px-1" style={{ color: 'var(--text-3)' }}>
          The analysis
        </h2>

        {landscape?.score_distribution && (
          <Section title="Score Distribution">
            <p className="text-[0.88rem] leading-relaxed mb-3" style={{ color: 'var(--text-2)' }}>
              Engagement follows a <strong>long tail distribution</strong> — most posts score under 50,
              while a tiny fraction of viral content captures the bulk of attention.
            </p>
            <img src="/blog/score_distribution.png" width={1480} height={730} loading="lazy" decoding="async" alt="Histogram of post scores: most posts score under 50, with a long tail of rare viral posts" className="chart-img w-full h-auto rounded-lg mb-3" style={{ background: 'var(--surface)' }} />
            <div className="grid grid-cols-5 gap-2 max-w-md text-[0.88rem]">
              {['mean','median','p75','p90','max'].map(k => (
                <div key={k} className="flex flex-col items-center">
                  <span className="text-lg md:text-xl font-black tabular-nums" style={{ color: 'var(--blue)', fontFamily: 'var(--font-display)' }}>
                    {Number(landscape.score_distribution[k as keyof typeof landscape.score_distribution]).toLocaleString()}
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
            <img src="/blog/category_breakdown.png" width={1484} height={880} loading="lazy" decoding="async" alt="Bar chart of confession counts by hashtag category" className="chart-img w-full h-auto rounded-lg mb-3" style={{ background: 'var(--surface)' }} />
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
            <img src="/blog/umap_landscape.webp" width={1600} height={724} loading="lazy" decoding="async" alt="UMAP scatter plot of all confessions, coloured by viral status and score intensity" className="chart-img w-full h-auto rounded-lg mb-3" style={{ background: 'var(--surface)' }} />
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
              const barColor = isPositive ? 'var(--fill)' : 'var(--orange)';
              const barInk = isPositive ? 'var(--on-fill)' : 'var(--on-orange)';
              const pctColor = isPositive ? 'var(--blue)' : 'var(--orange)';
              return (
                <div key={f.feature} className="flex items-center gap-2 text-[0.82rem] mb-2.5">
                  <span className="w-24 sm:w-36 text-right shrink-0 truncate font-medium" style={{ color: 'var(--text-1)' }}>
                    {f.feature}
                  </span>
                  <div className="h-[18px] rounded-sm flex-1 min-w-0" style={{ background: 'var(--surface-mid)' }}>
                    <div className="h-full rounded-sm flex items-center px-1.5 text-[0.68rem] font-bold tabular-nums whitespace-nowrap"
                         style={{ width: `${Math.min(pct, 100)}%`, background: barColor, color: barInk }}>
                      {pct > 12 ? `${isPositive ? '+' : ''}${f.boost}` : ''}
                    </div>
                  </div>
                  <span className="text-[0.68rem] w-12 sm:w-14 shrink-0 tabular-nums" style={{ color: 'var(--text-muted)' }}>
                    r={f.correlation}
                  </span>
                  {pct <= 12 && (
                    <span className="text-[0.72rem] font-bold shrink-0" style={{ color: pctColor }}>
                      {isPositive ? '+' : ''}{f.boost}
                    </span>
                  )}
                  {f.has_pct !== undefined && (
                    <span className="hidden sm:inline text-[0.68rem] w-14 shrink-0" style={{ color: 'var(--text-muted)' }}>
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
              Average score by time of day and day of week. Hours are in UTC (Singapore is UTC+8).
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
                  <span className="w-24 sm:w-36 text-right shrink-0 truncate font-medium" style={{ color: 'var(--text-1)' }}>
                    {c.category}
                  </span>
                  <div className="h-[18px] rounded-sm flex-1 min-w-0" style={{ background: 'var(--surface-mid)' }}>
                    <div className="h-full rounded-sm flex items-center px-1.5 text-[0.68rem] font-bold tabular-nums whitespace-nowrap"
                         style={{ width: `${(c.viral_rate / maxCatViral) * 100}%`, background: 'var(--orange)', color: 'var(--on-orange)' }}>
                      {(c.viral_rate / maxCatViral) > 0.3 ? `${(c.viral_rate * 100).toFixed(0)}%` : ''}
                    </div>
                  </div>
                  <span className="text-[0.68rem] w-9 shrink-0 tabular-nums" style={{ color: 'var(--text-muted)' }}>
                    {(c.viral_rate / maxCatViral) <= 0.3 ? `${(c.viral_rate * 100).toFixed(0)}%` : ''}
                  </span>
                  <span className="hidden sm:inline w-28 text-right text-[0.68rem] shrink-0 tabular-nums" style={{ color: 'var(--text-muted)' }}>
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
              Longer posts perform significantly better — <strong>long posts (&gt;80 words) average{' '}
              {insights.length_impact.find((l: any) => l.label === 'long')?.avg_score ?? ''}</strong>,
              nearly double the medium post average.
            </p>
            <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))' }}>
              {insights.length_impact.map((l: any) => (
                <div key={l.label} className="rounded-lg p-3 text-center"
                     style={{ background: 'var(--surface-alt)' }}>
                  <div className="text-xl font-black" style={{ color: l.label === 'long' ? 'var(--orange)' : 'var(--blue)', fontFamily: 'var(--font-display)' }}>
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
            <div className="divide-y divide-[var(--border)]">
              {landscape.top_posts.map((post: any, i: number) => (
                <Link key={post.id} href={`/post/${post.id}`}
                   className="list-row flex items-start gap-3 px-2 py-2.5 no-underline rounded-lg"
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
                </Link>
              ))}
            </div>
          </Section>
        )}

        {copypasta?.clusters?.length > 0 && (
          <Section title="Copypasta Watch">
            <p className="text-[0.88rem] leading-relaxed mb-4" style={{ color: 'var(--text-2)' }}>
              Repeated templates and copypastas circulating in the channel. <strong>{copypasta.exact_duplicates.total_duplicate_posts.toLocaleString()} posts</strong> ({copypasta.exact_duplicates.unique_texts} unique texts) are exact duplicates — <strong>{copypasta.exact_duplicates.pct_of_all_posts}%</strong> of all confessions.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 rounded-xl border mb-4 overflow-hidden" style={{ borderColor: 'var(--border)' }}>
              <OverviewStat val={String(copypasta.clusters.length)} lbl="Templates" />
              <OverviewStat val={copypasta.exact_duplicates.unique_texts.toLocaleString()} lbl="Unique repeated texts" />
              <OverviewStat val={copypasta.exact_duplicates.total_duplicate_posts.toLocaleString()} lbl="Duplicate posts" />
              <OverviewStat val={`${copypasta.exact_duplicates.pct_of_all_posts}%`} lbl="Of all posts" />
            </div>
            <div className="space-y-2">
              {copypasta.clusters.map((c: any) => (
                <Link key={c.key} href={`/post/${c.sample_id}`}
                   className="list-row flex items-start gap-2.5 px-2 py-2.5 no-underline rounded-lg"
                   style={{ color: 'var(--text-1)' }}>
                  <div className="flex flex-col items-center gap-0.5 w-14 shrink-0 mt-0.5">
                    <span className="text-base font-semibold leading-none tabular-nums" style={{ color: 'var(--text-1)' }}>{c.count}</span>
                    <span className="text-[0.66rem]" style={{ color: 'var(--text-muted)' }}>posts</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span className="font-semibold text-[0.82rem]">{c.name}</span>
                      {c.is_trending && (
                        <span className="text-[0.6rem] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded-sm"
                              style={{ background: 'var(--orange)', color: 'var(--on-orange)' }}>Trending</span>
                      )}
                    </div>
                    <div className="text-[0.75rem] leading-snug line-clamp-2" style={{ color: 'var(--text-muted)' }}>
                      &ldquo;{c.sample_text.slice(0, 150)}{c.sample_text.length > 150 ? '…' : ''}&rdquo;
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-[0.68rem]" style={{ color: 'var(--text-3)' }}>
                      <span>avg score <strong style={{ color: 'var(--blue)' }}>{c.avg_score}</strong></span>
                      <span>avg reactions <strong style={{ color: 'var(--blue)' }}>{c.avg_reactions}</strong></span>
                      <span>{c.trend_30d} in last 30d</span>
                    </div>
                  </div>
                  <span className="text-[0.65rem] shrink-0 mt-0.5" style={{ color: 'var(--text-muted)' }}>#{c.sample_id}</span>
                </Link>
              ))}
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
