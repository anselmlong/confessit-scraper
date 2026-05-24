export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

import { Nav } from '@/components/Nav';
import { FilterBar } from '@/components/FilterBar';
import { ConfessionCard } from '@/components/ConfessionCard';
import { StatsGrid } from '@/components/StatsGrid';
import { BarChart } from '@/components/BarChart';
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

      <main className="max-w-5xl mx-auto px-3 md:px-4 pb-12 md:pb-16 pt-4 md:pt-6">
        <FilterBar sort={sort} range={range} n={n} q={q} order={order} start_date={start_date || ''} end_date={end_date || ''} total={total} />

        <div className="mb-5">
          {posts.length === 0 ? (
            <p className="text-center py-10 text-[0.92rem]" style={{ color: 'var(--text-muted)' }}>
              {q ? `Nothing found for "${q}" — try a broader term or different time range.`
                 : `Quiet ${range}. Everyone's studying (probably).`}
            </p>
          ) : (
            posts.map((p, i) => (<ConfessionCard key={p.id} post={p} rank={i + 1} q={q} />))
          )}
        </div>
      </main>
    </>
  );
}
