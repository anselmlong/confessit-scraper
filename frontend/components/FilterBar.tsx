'use client';

import { useRouter } from 'next/navigation';
import { useTransition } from 'react';
import type { SortKey, RangeKey, OrderKey } from '@/lib/types';

interface FilterBarProps {
  sort: SortKey;
  range: RangeKey;
  n: number;
  q: string;
  order: OrderKey;
  mode: 'keyword' | 'semantic';
  start_date: string;
  end_date: string;
  total?: number;
}

const SORTS: { key: SortKey; label: string }[] = [
  { key: 'reactions', label: 'Reactions' },
  { key: 'replies',   label: 'Replies' },
  { key: 'score',     label: 'Score' },
  { key: 'time',      label: 'Time' },
];

const RANGES: { key: RangeKey; label: string }[] = [
  { key: 'week',  label: 'This Week' },
  { key: 'month', label: 'This Month' },
  { key: 'year',  label: 'This Year' },
  { key: 'all',   label: 'All Time' },
  { key: 'custom', label: 'Custom' },
];

const N_OPTIONS = [25, 50, 100];

export function FilterBar({ sort, range, n, q, order, mode, start_date, end_date, total }: FilterBarProps) {
  const router = useRouter();
  const [, startTransition] = useTransition();

  const navigate = (overrides: Partial<{ sort: string; range: string; n: number; q: string; order: string; mode: string; start_date: string; end_date: string }>) => {
    const base: Record<string, string> = { sort, range, n: String(n), q, order, mode };
    if (start_date) base.start_date = start_date;
    if (end_date) base.end_date = end_date;
    const p = new URLSearchParams(base);
    Object.entries(overrides).forEach(([k, v]) => p.set(k, String(v)));
    const newRange = overrides.range ?? range;
    if (newRange !== 'custom') {
      p.delete('start_date');
      p.delete('end_date');
    }
    if (p.get('mode') !== 'semantic') p.delete('mode');
    startTransition(() => router.push(`/?${p}`));
  };

  const toggleOrder = () => {
    navigate({ order: order === 'desc' ? 'asc' : 'desc' });
  };

  const pillBase =
    'text-[0.75rem] md:text-[0.81rem] font-semibold px-2 md:px-3 py-1 md:py-1.5 rounded-full border-[1.5px] no-underline ' +
    'pointer-coarse:min-h-10 pointer-coarse:px-3 transition-colors cursor-pointer whitespace-nowrap';
  const pillActive = 'text-[var(--on-fill)] border-[var(--fill)] bg-[var(--fill)]';
  const pillInactive =
    'text-[var(--text-2)] border-[var(--border)] hover:border-[var(--blue)] hover:text-[var(--blue)]';

  return (
    <div className="rounded-xl p-4 md:p-5 shadow-sm mb-4 md:mb-5" style={{ background: 'var(--surface)' }}>
      {/* Search */}
      <form
        onSubmit={e => {
          e.preventDefault();
          const fd = new FormData(e.currentTarget);
          navigate({ q: String(fd.get('q') ?? '') });
        }}
        className="flex flex-wrap items-center gap-2"
        role="search"
      >
        <div
          className="flex rounded-lg border-[1.5px] overflow-hidden shrink-0"
          style={{ borderColor: 'var(--border)' }}
          role="group"
          aria-label="Search mode"
        >
          {(['keyword', 'semantic'] as const).map(m => (
            <button
              key={m}
              type="button"
              onClick={() => mode !== m && navigate({ mode: m })}
              aria-pressed={mode === m}
              className="px-3 py-2 md:py-2.5 text-[0.75rem] md:text-[0.78rem] font-semibold border-none cursor-pointer transition-colors"
              style={mode === m
                ? { background: 'var(--fill)', color: 'var(--on-fill)' }
                : { background: 'transparent', color: 'var(--text-3)' }}
            >
              {m === 'keyword' ? 'Keyword' : 'Semantic'}
            </button>
          ))}
        </div>
        <div className="flex flex-1 min-w-[15rem] items-center gap-2">
        <input
          name="q"
          key={`search-${q}`}
          defaultValue={q}
          aria-label={mode === 'semantic' ? 'Describe what you’re looking for' : 'Search confessions'}
          placeholder={mode === 'semantic' ? 'Describe what you’re looking for…' : 'Search confessions…'}
          className="search-input flex-1 min-w-0 px-3 md:px-4 py-2 md:py-2.5 rounded-lg text-[0.85rem] md:text-[0.92rem] border-[1.5px] font-[inherit]"
          style={{
            background: 'var(--surface)',
            color: 'var(--text-1)',
            borderColor: 'var(--border)',
          }}
        />
        <button
          type="submit"
          className="shrink-0 px-4 md:px-5 py-2 md:py-2.5 rounded-lg font-semibold text-[0.82rem] md:text-[0.88rem] border-none cursor-pointer
                     transition-transform hover:-translate-y-px active:translate-y-px"
          style={{ background: 'var(--fill)', color: 'var(--on-fill)' }}
        >
          Search
        </button>
        {q && (
          <button
            type="button"
            onClick={() => navigate({ q: '' })}
            aria-label="Clear search"
            className="w-9 h-9 rounded-full flex items-center justify-center text-xs border-[1.5px] shrink-0
                       cursor-pointer transition-colors hover:border-[var(--text-2)] hover:text-[var(--text-1)]"
            style={{
              borderColor: 'var(--border)',
              color: 'var(--text-muted)',
              background: 'transparent',
            }}
          >
            <span aria-hidden="true">✕</span>
          </button>
        )}
        </div>
      </form>

      {/* Sort + Direction toggle */}
      <div
        className="flex gap-4 flex-wrap items-center mt-3.5 pt-3.5 border-t"
        style={{ borderColor: 'var(--border-light)' }}
      >
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="text-[0.7rem] font-bold uppercase tracking-wide whitespace-nowrap"
            style={{ color: 'var(--text-muted)' }}
          >
            Sort
          </span>
          <div className="flex gap-1.5 flex-wrap items-center">
            {SORTS.map(({ key, label }) => (
              key === 'score' ? (
                <div key={key} className="relative group">
                  <button
                    onClick={() => sort === key ? toggleOrder() : navigate({ sort: key, order: 'desc' })}
                    aria-pressed={sort === key}
                    aria-describedby="score-formula"
                    className={`${pillBase} ${sort === key ? pillActive : pillInactive}`}
                  >
                    {sort === key ? (order === 'desc' ? '↓ ' : '↑ ') : ''}{label}
                  </button>
                  <div
                    id="score-formula"
                    role="tooltip"
                    className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1.5 rounded-lg text-[0.72rem] whitespace-nowrap pointer-events-none opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity z-10"
                    style={{ background: 'var(--surface-alt)', color: 'var(--text-2)', border: '1px solid var(--border)' }}
                  >
                    reactions + replies × 2 + forwards × 3
                  </div>
                </div>
              ) : (
                <button
                  key={key}
                  onClick={() => sort === key ? toggleOrder() : navigate({ sort: key, order: 'desc' })}
                  aria-pressed={sort === key}
                  className={`${pillBase} ${sort === key ? pillActive : pillInactive}`}
                >
                  {sort === key ? (order === 'desc' ? '↓ ' : '↑ ') : ''}{label}
                </button>
              )
            ))}
          </div>
        </div>

        <div className="hidden md:block w-px h-5 shrink-0" aria-hidden="true" style={{ background: 'var(--border)' }} />

        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="text-[0.7rem] font-bold uppercase tracking-wide whitespace-nowrap"
            style={{ color: 'var(--text-muted)' }}
          >
            When
          </span>
          <div className="flex gap-1.5 flex-wrap">
            {RANGES.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => navigate({ range: key })}
                aria-pressed={range === key}
                className={`${pillBase} ${range === key ? pillActive : pillInactive}`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Custom date inputs */}
      {range === 'custom' && (
        <div className="flex gap-2 flex-wrap items-center mt-3 pt-3 border-t" style={{ borderColor: 'var(--border-light)' }}>
          <input
            key={`sd-${start_date}`}
            type="date"
            defaultValue={start_date}
            onChange={e => navigate({ start_date: e.target.value, range: 'custom' })}
            aria-label="From date"
            className="search-input px-3 py-1.5 pointer-coarse:py-2 rounded-lg text-[0.82rem] border-[1.5px] font-[inherit]"
            style={{ background: 'var(--surface)', color: 'var(--text-1)', borderColor: 'var(--border)' }}
          />
          <span className="text-[0.78rem]" aria-hidden="true" style={{ color: 'var(--text-muted)' }}>→</span>
          <input
            key={`ed-${end_date}`}
            type="date"
            defaultValue={end_date}
            onChange={e => navigate({ end_date: e.target.value, range: 'custom' })}
            aria-label="To date"
            className="search-input px-3 py-1.5 pointer-coarse:py-2 rounded-lg text-[0.82rem] border-[1.5px] font-[inherit]"
            style={{ background: 'var(--surface)', color: 'var(--text-1)', borderColor: 'var(--border)' }}
          />
        </div>
      )}

      {/* Results meta + N pills */}
      <div className="flex justify-between items-center flex-wrap gap-2 md:gap-3 mt-2.5 md:mt-3">
        <p className="text-[0.78rem] md:text-[0.83rem] m-0" style={{ color: 'var(--text-3)' }}>
          {q ? (
            <>
              Results for{' '}
              <strong style={{ color: 'var(--text-1)' }}>&ldquo;{q}&rdquo;</strong>
            </>
          ) : (
            <>
              Showing top{' '}
              <strong style={{ color: 'var(--text-1)' }}>{n}</strong>
              {total != null && <> of <strong style={{ color: 'var(--text-1)' }}>{total.toLocaleString()}</strong></>}
              {range !== 'custom' && (
                <> &middot; sorted by <strong style={{ color: 'var(--orange)' }}>{order === 'desc' ? '↓' : '↑'} {sort}</strong></>
              )}
            </>
          )}
        </p>
        <div className="flex gap-1 md:gap-1.5" role="group" aria-label="Posts per page">
          {N_OPTIONS.map(val => (
            <button
              key={val}
              onClick={() => navigate({ n: val })}
              aria-pressed={n === val}
              aria-label={`Show ${val} posts`}
              className={`text-[0.72rem] md:text-[0.78rem] px-2 md:px-3 py-1 md:py-1.5 pointer-coarse:min-h-10 pointer-coarse:min-w-11 rounded-xl border-[1.5px] cursor-pointer transition-colors
                ${n === val
                  ? 'text-[var(--on-fill)] border-[var(--fill)] bg-[var(--fill)]'
                  : 'text-[var(--text-2)] border-[var(--border)] hover:border-[var(--blue)] hover:text-[var(--blue)]'}`}
            >
              {val}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
