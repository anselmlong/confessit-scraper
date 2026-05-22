export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

import { Nav } from '@/components/Nav';
import { FilterBar } from '@/components/FilterBar';
import { ConfessionCard } from '@/components/ConfessionCard';
import { StatsGrid } from '@/components/StatsGrid';
import { BarChart } from '@/components/BarChart';
import { TimeTagline } from '@/components/TimeTagline';
import { getPosts, getPostCount, getStats, getMonthlyCounts } from '@/lib/db';
import type { Post, Stats, MonthlyCount, SortKey, RangeKey } from '@/lib/types';

const VALID_SORTS: SortKey[] = ['reactions', 'replies', 'score'];
const VALID_RANGES: RangeKey[] = ['week', 'month', 'year', 'all'];
const API_BASE = process.env.NEXT_PUBLIC_VPS_API || '';

/* ── VPS API helpers ──────────────────────────────── */

async function vpsPosts(opts: { sort: SortKey; range: RangeKey; limit: number; q?: string }): Promise<Post[] | null> {
  if (!API_BASE) return null;
  const p = new URLSearchParams({ sort: opts.sort, range: opts.range, n: String(opts.limit) });
  if (opts.q) p.set('q', opts.q);
  try {
    const r = await fetch(`${API_BASE}/api/posts?${p}`, { next: { revalidate: 300 } });
    if (!r.ok) return null;
    const data = await r.json();
    return data.map((d: any): Post => ({
      id: d.id, message_id: null, date: d.date, text: null, content: null,
      title: d.title || null, category: d.category || null, confession_id: null,
      reactions_count: d.reactions, reply_count: d.replies, forwards: d.forwards || 0,
      views: 0, is_reply: 0, reply_to_msg_id: null, word_count: null,
      score: d.score, excerpt: d.excerpt,
    }));
  } catch { return null; }
}

async function vpsStats(): Promise<Stats | null> {
  if (!API_BASE) return null;
  try {
    const r = await fetch(`${API_BASE}/api/stats`, { next: { revalidate: 300 } });
    if (!r.ok) return null;
    const d = await r.json();
    return {
      total: d.total_posts, first_date: d.first_date, last_date: d.last_date,
      total_views: d.total_views, avg_reactions: d.avg_reactions, avg_words: d.avg_words,
      max_reactions: d.max_reactions, total_replies: d.total_replies, days_active: d.days_active,
    };
  } catch { return null; }
}

async function vpsMonthly(): Promise<MonthlyCount[] | null> {
  if (!API_BASE) return null;
  try {
    const r = await fetch(`${API_BASE}/api/monthly`, { next: { revalidate: 300 } });
    if (!r.ok) return null;
    const data = await r.json();
    return data.map((m: any): MonthlyCount => ({ month: m.month, cnt: m.count }));
  } catch { return null; }
}

/* ── Main Page ────────────────────────────────────── */

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ sort?: string; range?: string; n?: string; q?: string }>;
}) {
  const sp = await searchParams;
  const sort: SortKey = VALID_SORTS.includes(sp.sort as SortKey) ? (sp.sort as SortKey) : 'reactions';
  const range: RangeKey = VALID_RANGES.includes(sp.range as RangeKey) ? (sp.range as RangeKey) : 'month';
  const n = Math.min(Math.max(parseInt(sp.n ?? '25', 10) || 25, 1), 200);
  const q = (sp.q ?? '').trim();

  // Try VPS API first, fall back to local SQLite
  const [remotePosts, remoteStats, remoteMonthly] = await Promise.all([
    vpsPosts({ sort, range, limit: n, q: q || undefined }),
    vpsStats(),
    vpsMonthly(),
  ]);

  const posts = remotePosts ?? getPosts({ range, sort, q: q || undefined, limit: n });
  const stats = remoteStats ?? getStats();
  const monthly = remoteMonthly ?? getMonthlyCounts().map(m => ({ month: m.month, cnt: m.cnt }));
  const total = remoteStats?.total ?? getPostCount({ range, q: q || undefined });

  return (
    <>
      <Nav activePage="home" />

      {/* Hero header */}
      <header
        className="text-white px-6 py-8"
        style={{ background: 'linear-gradient(135deg, #003D7C 0%, #00509E 100%)' }}
      >
        <div className="max-w-5xl mx-auto">
          <h1 className="text-2xl font-bold">NUSConfessIT</h1>
          <p className="text-white/75 mt-1.5 text-sm">
            {stats.total.toLocaleString()} confessions &middot; {stats.first_date} to {stats.last_date}
          </p>
          <TimeTagline />
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 pb-16 pt-6">
        <FilterBar sort={sort} range={range} n={n} q={q} />

        {/* Results count */}
        {!q && (
          <p className="text-[0.83rem] mb-4" style={{ color: 'var(--text-3)' }}>
            Top{' '}
            <strong style={{ color: 'var(--text-1)' }}>{n}</strong>
            {' '}of{' '}
            <strong style={{ color: 'var(--text-1)' }}>{total.toLocaleString()}</strong>
            {posts[0] && (
              <>
                {' '}&middot; top {sort}:{' '}
                <strong style={{ color: 'var(--orange)' }}>
                  {sort === 'reactions'
                    ? posts[0].reactions_count
                    : sort === 'replies'
                    ? posts[0].reply_count
                    : posts[0].score}
                </strong>
              </>
            )}
          </p>
        )}

        {/* Confession list */}
        <div className="rounded-xl p-5 shadow-sm mb-5" style={{ background: 'var(--surface)' }}>
          {posts.length === 0 ? (
            <p
              className="text-center py-10 text-[0.92rem]"
              style={{ color: 'var(--text-muted)' }}
            >
              {q
                ? `Nothing found for "${q}" — try a broader term or different time range.`
                : `Quiet ${range}. Everyone's studying (probably).`}
            </p>
          ) : (
            posts.map((p, i) => (
              <ConfessionCard key={p.id} post={p} rank={i + 1} q={q} />
            ))
          )}
        </div>

        {/* Stats card */}
        <section className="rounded-xl p-5 shadow-sm mb-5" style={{ background: 'var(--surface)' }}>
          <h2
            className="text-[0.85rem] font-bold uppercase tracking-[0.8px] mb-4 pb-2 inline-block border-b-2"
            style={{ color: 'var(--blue)', borderColor: 'var(--orange)' }}
          >
            Channel Stats
          </h2>
          <StatsGrid stats={stats} />
        </section>

        {/* Monthly activity */}
        <section className="rounded-xl p-5 shadow-sm" style={{ background: 'var(--surface)' }}>
          <h2
            className="text-[0.85rem] font-bold uppercase tracking-[0.8px] mb-4 pb-2 inline-block border-b-2"
            style={{ color: 'var(--blue)', borderColor: 'var(--orange)' }}
          >
            Monthly Activity
          </h2>
          <BarChart data={monthly} />
        </section>
      </main>
    </>
  );
}