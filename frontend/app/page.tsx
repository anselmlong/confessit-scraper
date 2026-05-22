export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

import { Nav } from '@/components/Nav';
import { FilterBar } from '@/components/FilterBar';
import { ConfessionCard } from '@/components/ConfessionCard';
import { StatsGrid } from '@/components/StatsGrid';
import { BarChart } from '@/components/BarChart';
import { TimeTagline } from '@/components/TimeTagline';
import { getPosts, getStats, getMonthlyCounts } from '@/lib/api';
import type { SortKey, RangeKey } from '@/lib/types';

const VALID_SORTS: SortKey[] = ['reactions', 'replies', 'score', 'time'];
const VALID_RANGES: RangeKey[] = ['week', 'month', 'year', 'all', 'custom'];

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ sort?: string; range?: string; n?: string; q?: string; order?: string; start_date?: string; end_date?: string }>;
}) {
  const sp = await searchParams;
  const sort: SortKey = VALID_SORTS.includes(sp.sort as SortKey) ? (sp.sort as SortKey) : 'reactions';
  const range: RangeKey = VALID_RANGES.includes(sp.range as RangeKey) ? (sp.range as RangeKey) : 'month';
  const n = Math.min(Math.max(parseInt(sp.n ?? '25', 10) || 25, 1), 200);
  const q = (sp.q ?? '').trim();
  const order = sp.order === 'asc' ? 'asc' : 'desc';
  const start_date = (sp.start_date ?? '').trim() || undefined;
  const end_date = (sp.end_date ?? '').trim() || undefined;

  const [posts, stats, monthly] = await Promise.all([
    getPosts({ sort, range, limit: n, q: q || undefined, order, start_date, end_date }),
    getStats(),
    getMonthlyCounts(),
  ]);

  const total = stats?.total ?? 0;

  return (
    <>
      <Nav activePage="home" />
      <header className="text-white px-4 md:px-6 py-5 md:py-8" style={{ background: 'linear-gradient(135deg, #003D7C 0%, #00509E 100%)' }}>
        <div className="max-w-5xl mx-auto">
          <h1 className="text-lg md:text-2xl font-bold leading-snug">NUSConfessIT</h1>
          <p className="text-white/75 mt-1 text-sm">
            {total.toLocaleString()} confessions
          </p>
          <TimeTagline />
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 md:px-4 pb-12 md:pb-16 pt-4 md:pt-6">
        <FilterBar sort={sort} range={range} n={n} q={q} order={order} start_date={start_date || ''} end_date={end_date || ''} />

        {!q && (
          <p className="text-[0.83rem] mb-4" style={{ color: 'var(--text-3)' }}>
            Top <strong style={{ color: 'var(--text-1)' }}>{n}</strong> of{' '}
            <strong style={{ color: 'var(--text-1)' }}>{total.toLocaleString()}</strong>
            {posts[0] && (
              <> &middot; top {sort}:{' '}
                <strong style={{ color: 'var(--orange)' }}>
                  {sort === 'reactions' ? posts[0].reactions_count
                    : sort === 'replies' ? posts[0].reply_count
                    : posts[0].score}
                </strong>
              </>
            )}
          </p>
        )}

        <div className="rounded-xl p-5 shadow-sm mb-5" style={{ background: 'var(--surface)' }}>
          {posts.length === 0 ? (
            <p className="text-center py-10 text-[0.92rem]" style={{ color: 'var(--text-muted)' }}>
              {q ? `Nothing found for "${q}" — try a broader term or different time range.`
                 : `Quiet ${range}. Everyone's studying (probably).`}
            </p>
          ) : (
            posts.map((p, i) => (<ConfessionCard key={p.id} post={p} rank={i + 1} q={q} />))
          )}
        </div>

        {stats && (
          <section className="rounded-xl p-5 shadow-sm mb-5" style={{ background: 'var(--surface)' }}>
            <h2 className="text-[0.85rem] font-bold uppercase tracking-[0.8px] mb-4 pb-2 inline-block border-b-2"
                style={{ color: 'var(--blue)', borderColor: 'var(--orange)' }}>
              Channel Stats
            </h2>
            <StatsGrid stats={stats} />
          </section>
        )}

        {monthly.length > 0 && (
          <section className="rounded-xl p-5 shadow-sm" style={{ background: 'var(--surface)' }}>
            <h2 className="text-[0.85rem] font-bold uppercase tracking-[0.8px] mb-4 pb-2 inline-block border-b-2"
                style={{ color: 'var(--blue)', borderColor: 'var(--orange)' }}>
              Monthly Activity
            </h2>
            <BarChart data={monthly} />
          </section>
        )}
      </main>
    </>
  );
}