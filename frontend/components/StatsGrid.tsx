import type { Stats } from '@/lib/types';

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return n.toLocaleString();
}

export function StatsGrid({ stats }: { stats: Stats }) {
  const items = [
    { val: stats.total.toLocaleString(), lbl: 'Total Posts' },
    { val: fmt(stats.total_views),       lbl: 'Total Views' },
    { val: String(stats.avg_reactions),  lbl: 'Avg Reactions' },
    { val: String(stats.avg_words),      lbl: 'Avg Words' },
    { val: String(stats.max_reactions),  lbl: 'Most Reactions' },
    { val: String(stats.days_active),    lbl: 'Days Active' },
    { val: fmt(stats.total_replies),     lbl: 'Replies Stored' },
  ];

  return (
    <div
      className="grid gap-3"
      style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))' }}
    >
      {items.map(({ val, lbl }) => (
        <div
          key={lbl}
          className="rounded-lg p-4 text-center border-t-[3px] transition-colors"
          style={{ background: 'var(--surface-alt)', borderColor: 'var(--blue)' }}
        >
          <div className="text-2xl font-black break-words" style={{ color: 'var(--blue)' }}>
            {val}
          </div>
          <div
            className="text-[0.7rem] uppercase tracking-wide mt-1"
            style={{ color: 'var(--text-3)' }}
          >
            {lbl}
          </div>
        </div>
      ))}
    </div>
  );
}
