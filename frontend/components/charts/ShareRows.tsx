'use client';

import Link from 'next/link';
import { useState } from 'react';
import type { SharePoint } from '@/lib/types';
import { fmtDay, useWidth } from './useWidth';

export interface ShareRow {
  label: string;
  total: number;
  series: SharePoint[];
  peak?: { month: string; share: number } | null;
  /** Shown when not hovering, in place of the peak. */
  summary?: string;
}

const ROW_H = 46;
const LABEL_W = 168;

function monthEnd(m: string) {
  const [y, mo] = m.split('-').map(Number);
  return `${m}-${String(new Date(Date.UTC(y, mo, 0)).getUTCDate()).padStart(2, '0')}`;
}

/**
 * Small multiples of "share of posts per month", one row per series, sharing an
 * x-axis and a hover month. Each row has its own y-scale (its peak is stated in
 * the label), so shapes compare honestly and small series stay readable.
 */
export function ShareRows({ rows, months, linkTerms = false, emptyNote }: {
  rows: ShareRow[]; months: string[]; linkTerms?: boolean; emptyNote?: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const [ref, width] = useWidth<HTMLDivElement>();
  const narrow = width < 520;
  const labelW = narrow ? 0 : LABEL_W;
  const chartW = Math.max(width - labelW, 40);
  const step = chartW / Math.max(months.length - 1, 1);
  const x = (i: number) => i * step;

  const yearTicks = months
    .map((m, i) => ({ m, i }))
    .filter(({ m, i }) => m.endsWith('-01') || i === 0);

  if (!rows.length) {
    return <p className="text-[0.86rem] py-6 text-center" style={{ color: 'var(--text-muted)' }}>{emptyNote ?? 'Nothing to show.'}</p>;
  }

  const hoverMonth = hover !== null ? months[hover] : null;

  return (
    <div ref={ref} onMouseLeave={() => setHover(null)}>
      <div className="flex items-center justify-between text-[0.74rem] mb-1 h-5" style={{ color: 'var(--text-muted)' }}>
        <span>{hoverMonth ? fmtDay(hoverMonth, { month: 'long', year: 'numeric' }) : 'Hover a month to compare'}</span>
        {linkTerms && hoverMonth && <span className="max-sm:hidden">Click to read that month&rsquo;s posts</span>}
      </div>

      {rows.map((r, ri) => {
        const max = Math.max(...r.series.map(p => p.share), 0.0001);
        const yy = (v: number) => ROW_H - 4 - (v / max) * (ROW_H - 10);
        const pts = r.series.map((p, i) => `${x(i)},${yy(p.share)}`).join(' ');
        const hp = hover !== null ? r.series[hover] : null;
        const gid = `fill-${ri}`;
        return (
          <div key={r.label} className={`border-t ${narrow ? 'py-2' : 'flex items-center'}`} style={{ borderColor: 'var(--border-light)' }}>
            <div className={`${narrow ? 'flex justify-between items-baseline mb-1' : 'shrink-0 pr-4'}`} style={narrow ? undefined : { width: labelW }}>
              <div className="text-[0.86rem] font-medium truncate" style={{ color: 'var(--text-1)' }}>{r.label}</div>
              <div className="text-[0.72rem] tabular-nums" style={{ color: 'var(--text-muted)' }}>
                {hp
                  ? <><span style={{ color: 'var(--text-1)' }}>{hp.share}%</span> · {hp.count.toLocaleString()} posts</>
                  : r.summary ? r.summary
                  : r.peak
                    ? <>peak {r.peak.share}% · {fmtDay(r.peak.month, { month: 'short', year: '2-digit' })}</>
                    : <>{r.total.toLocaleString()} posts</>}
              </div>
            </div>
            <svg width={chartW} height={ROW_H} className="block overflow-visible" role="img"
                 aria-label={`${r.label}: share of posts per month, peaking at ${max}%`}>
              <defs>
                <linearGradient id={gid} x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0" stopColor="var(--blue)" stopOpacity="0.28" />
                  <stop offset="1" stopColor="var(--blue)" stopOpacity="0.02" />
                </linearGradient>
              </defs>
              <polygon points={`0,${ROW_H - 4} ${pts} ${x(r.series.length - 1)},${ROW_H - 4}`} fill={`url(#${gid})`} />
              <polyline points={pts} fill="none" stroke="var(--blue)" strokeWidth={1.75} strokeLinejoin="round" />
              {hover !== null && hp && (
                <circle cx={x(hover)} cy={yy(hp.share)} r={3.5} fill="var(--blue)" stroke="var(--surface)" strokeWidth={2} />
              )}
              {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={0} y2={ROW_H} stroke="var(--text-muted)" strokeDasharray="2 3" />}
              {months.map((m, i) => {
                const w = step;
                const rect = (
                  <rect key={m} x={x(i) - w / 2} y={0} width={w} height={ROW_H} fill="transparent"
                        onMouseEnter={() => setHover(i)} className={linkTerms ? 'cursor-pointer' : undefined} />
                );
                return linkTerms ? (
                  <Link key={m} prefetch={false} href={`/?q=${encodeURIComponent(r.label)}&range=custom&start_date=${m}-01&end_date=${monthEnd(m)}&sort=score&n=100`}
                        aria-label={`Read posts mentioning ${r.label} in ${fmtDay(m, { month: 'long', year: 'numeric' })}`}>
                    {rect}
                  </Link>
                ) : rect;
              })}
            </svg>
          </div>
        );
      })}

      <div className="flex border-t pt-1" style={{ borderColor: 'var(--border)' }}>
        <div className="shrink-0" style={{ width: labelW }} />
        <div className="relative h-4" style={{ width: chartW }}>
          {yearTicks.map(({ m, i }) => (
            <span key={m} className="absolute text-[0.7rem] tabular-nums whitespace-nowrap" style={{ left: x(i), color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', transform: i === 0 ? undefined : 'translateX(-50%)' }}>
              {m.slice(0, 4)}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
