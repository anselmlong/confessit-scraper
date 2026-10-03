export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

import { Nav } from '@/components/Nav';
import { FilterBar } from '@/components/FilterBar';
import { ConfessionCard } from '@/components/ConfessionCard';
import { TimeTagline } from '@/components/TimeTagline';
import { EndOfList } from '@/components/EndOfList';
import { getPosts, getStats } from '@/lib/api';
import type { SortKey, RangeKey } from '@/lib/types';

const VALID_SORTS: SortKey[] = ['reactions', 'replies', 'score', 'time'];
const VALID_RANGES: RangeKey[] = ['week', 'month', 'year', 'all', 'custom'];

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ sort?: string; range?: string; n?: string; q?: string; order?: string; mode?: string; start_date?: string; end_date?: string }>;
}) {
  const sp = await searchParams;
  const sort: SortKey = VALID_SORTS.includes(sp.sort as SortKey) ? (sp.sort as SortKey) : 'time';
  const range: RangeKey = VALID_RANGES.includes(sp.range as RangeKey) ? (sp.range as RangeKey) : 'week';
  const n = Math.min(Math.max(parseInt(sp.n ?? '100', 10) || 100, 1), 200);
  const q = (sp.q ?? '').trim();
  const order = sp.order === 'asc' ? 'asc' : 'desc';
  const mode = sp.mode === 'semantic' ? 'semantic' : 'keyword';
  const start_date = (sp.start_date ?? '').trim() || undefined;
  const end_date = (sp.end_date ?? '').trim() || undefined;

  const [posts, stats] = await Promise.all([
    getPosts({ sort, range, limit: n, q: q || undefined, order, mode, start_date, end_date }),
    getStats(),
  ]);

  const total = stats?.total ?? 0;

  return (
    <>
      <Nav activePage="home" />

      <main className="max-w-5xl mx-auto px-3 md:px-4 pb-12 md:pb-16 pt-4 md:pt-6">
        <h1 className="sr-only">NUSConfessIT confessions</h1>
        <TimeTagline />
        <FilterBar sort={sort} range={range} n={n} q={q} order={order} mode={mode} start_date={start_date || ''} end_date={end_date || ''} total={total} />

        <div className="mb-5">
          {posts.length === 0 ? (
            <p role="status" className="text-center py-10 text-[0.92rem]" style={{ color: 'var(--text-muted)' }}>
              {q ? `Nothing found for "${q}" — try a broader term or different time range.`
                 : range === 'week'  ? `Nothing this week. Even confessions need a break.`
                 : range === 'month' ? `Quiet month. Everyone's studying (probably).`
                 : range === 'year'  ? `Not a word this year. Something happened.`
                 : `Silence. The archive is holding its breath.`}
            </p>
          ) : (
            <>
              <ol aria-label={q ? `Results for ${q}` : 'Confessions'}>
                {posts.map((p, i) => (<li key={p.id}><ConfessionCard post={p} rank={i + 1} q={q} /></li>))}
              </ol>
              <EndOfList count={posts.length} />
            </>
          )}
        </div>
      </main>
    </>
  );
}
