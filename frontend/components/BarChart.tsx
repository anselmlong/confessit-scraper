import type { MonthlyCount } from '@/lib/types';

export function BarChart({ data }: { data: MonthlyCount[] }) {
  const max = Math.max(...data.map(d => d.cnt), 1);

  return (
    <div className="mt-2 space-y-2">
      {data.map(({ month, cnt }, i) => (
        <div key={month} className="flex items-center gap-2.5 text-[0.78rem]">
          <span className="w-14 text-right shrink-0" style={{ color: 'var(--text-3)' }}>
            {month}
          </span>
          <div
            className="h-[22px] rounded-sm min-w-[2px]"
            style={{
              width: `${(cnt / max) * 100}%`,
              background: 'var(--blue)',
              animation: `bar-grow 0.55s cubic-bezier(0.22,1,0.36,1) ${i * 28}ms both`,
            }}
          />
          <span style={{ color: 'var(--text-3)', minWidth: '2rem' }}>{cnt}</span>
        </div>
      ))}
    </div>
  );
}
