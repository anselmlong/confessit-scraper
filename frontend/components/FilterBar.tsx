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

export function FilterBar({ sort, range, n, q, order, start_date, end_date, total }: FilterBarProps) {
  const router = useRouter();
  const [, startTransition] = useTransition();

  const navigate = (overrides: Partial<{ sort: string; range: string; n: number; q: string; order: string; start_date: string; end_date: string }>) => {
    const base: Record<string, string> = { sort, range, n: String(n), q, order };
    if (start_date) base.start_date = start_date;
    if (end_date) base.end_date = end_date;
    const p = new URLSearchParams(base);
    Object.entries(overrides).forEach(([k, v]) => p.set(k, String(v)));
    const newRange = overrides.range ?? range;
    if (newRange !== 'custom') {
      p.delete('start_date');
      p.delete('end_date');
    }
    startTransition(() => router.push(`/?${p}`));
  };

  const toggleOrder = () => {
    navigate({ order: order === 'desc' ? 'asc' : 'desc' });
  };

  const pillBase =
    'text-[0.75rem] md:text-[0.81rem] font-semibold px-2 md:px-3 py-1 md:py-1.5 rounded-full border-[1.5px] no-underline ' +
    'transition-all cursor-pointer whitespace-nowrap';
  const pillActive = 'text-white border-[var(--blue)] bg-[var(--blue)]';
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
        className="flex items-center gap-1.5 md:gap-2"
      >
        <input
          name="q"
          key={`search-${q}`}
          defaultValue={q}
          placeholder="Search confessions…"
          className="search-input flex-1 px-3 md:px-4 py-2 md:py-2.5 rounded-lg text-[0.85rem] md:text-[0.92rem] border-[1.5px] font-[inherit]"
          style={{
            background: 'var(--surface)',
            color: 'var(--text-1)',
            borderColor: 'var(--border)',
          }}
        />
        <button
          type="submit"
          className="px-3 md:px-5 py-2 md:py-2.5 rounded-lg font-semibold text-[0.82rem] md:text-[0.88rem] text-white border-none cursor-pointer
                     transition-all hover:-translate-y-px active:translate-y-px"
          style={{ background: 'var(--blue)' }}
        >
          Search
        </button>
        {q && (
          <button
            type="button"
            onClick={() => navigate({ q: '' })}
            aria-label="Clear search"
            className="w-7 h-7 rounded-full flex items-center justify-center text-xs border-[1.5px] shrink-0
                       cursor-pointer transition-all hover:border-[var(--text-2)] hover:text-[var(--text-1)]"
            style={{
              borderColor: 'var(--border)',
              color: 'var(--text-muted)',
              background: 'transparent',
            }}
          >
            ✕
          </button>
        )}
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
                    className={`${pillBase} ${sort === key ? pillActive : pillInactive}`}
                  >
                    {sort === key ? (order === 'desc' ? '↓ ' : '↑ ') : ''}{label}
                  </button>
                  <div
                    className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1.5 rounded-lg text-[0.72rem] whitespace-nowrap pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity z-10"
                    style={{ background: 'var(--surface-alt)', color: 'var(--text-2)', border: '1px solid var(--border)' }}
                  >
                    reactions + replies × 2 + forwards × 3
                  </div>
                </div>
              ) : (
                <button
                  key={key}
                  onClick={() => sort === key ? toggleOrder() : navigate({ sort: key, order: 'desc' })}
                  className={`${pillBase} ${sort === key ? pillActive : pillInactive}`}
                >
                  {sort === key ? (order === 'desc' ? '↓ ' : '↑ ') : ''}{label}
                </button>
              )
            ))}
          </div>
        </div>

        <div className="w-px h-5 shrink-0" style={{ background: 'var(--border)' }} />

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
            className="px-3 py-1.5 rounded-lg text-[0.82rem] border-[1.5px] outline-none font-[inherit]"
            style={{ background: 'var(--surface)', color: 'var(--text-1)', borderColor: 'var(--border)' }}
          />
          <span className="text-[0.78rem]" style={{ color: 'var(--text-muted)' }}>→</span>
          <input
            key={`ed-${end_date}`}
            type="date"
            defaultValue={end_date}
            onChange={e => navigate({ end_date: e.target.value, range: 'custom' })}
            className="px-3 py-1.5 rounded-lg text-[0.82rem] border-[1.5px] outline-none font-[inherit]"
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
        <div className="flex gap-1 md:gap-1.5">
          {N_OPTIONS.map(val => (
            <button
              key={val}
              onClick={() => navigate({ n: val })}
              className={`text-[0.72rem] md:text-[0.78rem] px-2 md:px-3 py-1 md:py-1.5 rounded-xl border-[1.5px] cursor-pointer transition-all
                ${n === val
                  ? 'text-white border-[var(--blue)] bg-[var(--blue)]'
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
