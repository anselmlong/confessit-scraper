'use client';

import { useRouter } from 'next/navigation';
import { useTransition } from 'react';
import type { SortKey, RangeKey } from '@/lib/types';

interface FilterBarProps {
  sort: SortKey;
  range: RangeKey;
  n: number;
  q: string;
}

const SORTS: { key: SortKey; label: string }[] = [
  { key: 'reactions', label: '❤ Reactions' },
  { key: 'replies',   label: '💬 Replies' },
  { key: 'score',     label: '✨ Score' },
  { key: 'time',      label: '🕐 Recent' },
];

const RANGES: { key: RangeKey; label: string }[] = [
  { key: 'week',  label: 'This Week' },
  { key: 'month', label: 'This Month' },
  { key: 'year',  label: 'This Year' },
  { key: 'all',   label: 'All Time' },
];

const N_OPTIONS = [25, 50, 100];

export function FilterBar({ sort, range, n, q }: FilterBarProps) {
  const router = useRouter();
  const [, startTransition] = useTransition();

  const navigate = (overrides: Partial<{ sort: string; range: string; n: number; q: string }>) => {
    const p = new URLSearchParams({ sort, range, n: String(n), q });
    Object.entries(overrides).forEach(([k, v]) => p.set(k, String(v)));
    startTransition(() => router.push(`/?${p}`));
  };

  const pillBase =
    'text-[0.81rem] font-semibold px-3 py-1.5 rounded-full border-[1.5px] no-underline ' +
    'transition-all cursor-pointer whitespace-nowrap';
  const pillActive = 'text-white border-[var(--blue)] bg-[var(--blue)]';
  const pillInactive =
    'text-[var(--text-2)] border-[var(--border)] hover:border-[var(--blue)] hover:text-[var(--blue)]';

  return (
    <div className="rounded-xl p-5 shadow-sm mb-5" style={{ background: 'var(--surface)' }}>
      {/* Search */}
      <form
        onSubmit={e => {
          e.preventDefault();
          const fd = new FormData(e.currentTarget);
          navigate({ q: String(fd.get('q') ?? '') });
        }}
        className="flex items-center gap-2"
      >
        <input
          name="q"
          key={`search-${q}`}
          defaultValue={q}
          placeholder="Search confessions… e.g. 'relationship', 'CS2030', 'internship'"
          className="flex-1 px-4 py-2.5 rounded-lg text-[0.92rem] border-[1.5px] outline-none font-[inherit]
                     transition-colors focus:border-[var(--blue)]"
          style={{
            background: 'var(--surface)',
            color: 'var(--text-1)',
            borderColor: 'var(--border)',
          }}
        />
        <button
          type="submit"
          className="px-5 py-2.5 rounded-lg font-semibold text-[0.88rem] text-white border-none cursor-pointer
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

      {/* Filter pills */}
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
          <div className="flex gap-1.5 flex-wrap">
            {SORTS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => navigate({ sort: key })}
                className={`${pillBase} ${sort === key ? pillActive : pillInactive}`}
              >
                {label}
              </button>
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

      {/* Results meta + N pills */}
      <div className="flex justify-between items-center flex-wrap gap-3 mt-3">
        <p className="text-[0.83rem] m-0" style={{ color: 'var(--text-3)' }}>
          {q ? (
            <>
              Results for{' '}
              <strong style={{ color: 'var(--text-1)' }}>&ldquo;{q}&rdquo;</strong>
            </>
          ) : (
            <>
              Showing top{' '}
              <strong style={{ color: 'var(--text-1)' }}>{n}</strong>
            </>
          )}
        </p>
        <div className="flex gap-1.5">
          {N_OPTIONS.map(val => (
            <button
              key={val}
              onClick={() => navigate({ n: val })}
              className={`text-[0.78rem] px-3 py-1.5 rounded-xl border-[1.5px] cursor-pointer transition-all
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
