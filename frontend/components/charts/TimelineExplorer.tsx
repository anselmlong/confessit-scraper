'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import type { Moment, Timeline, TimelineBucket } from '@/lib/types';
import { HeartIcon, ReplyIcon } from '@/components/Icons';
import { fmtDay, niceMax, useWidth } from './useWidth';

type Metric = 'count' | 'avg_score';

const METRICS: { key: Metric; label: string; unit: string }[] = [
  { key: 'count', label: 'Posts', unit: 'posts' },
  { key: 'avg_score', label: 'Avg engagement', unit: 'avg score' },
];

const H = 240;
const PAD = { top: 22, right: 4, bottom: 26, left: 40 };

function bucketLabel(b: TimelineBucket, kind: Timeline['bucket']) {
  if (kind === 'day') return fmtDay(b.start, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
  return `Week of ${fmtDay(b.start, { day: 'numeric', month: 'short', year: 'numeric' })}`;
}

function feedHref(start: string, end: string) {
  return `/?range=custom&start_date=${start}&end_date=${end}&sort=score&n=100`;
}

/** Bar with 4px rounded top corners, square at the baseline. */
function barPath(x: number, y: number, w: number, h: number) {
  if (h <= 0) return '';
  const r = Math.min(4, w / 2, h);
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}

export function TimelineExplorer({ data }: { data: Timeline }) {
  const { series, bucket } = data;
  const [metric, setMetric] = useState<Metric>('count');
  const [hover, setHover] = useState<number | null>(null);
  const lastComplete = useMemo(() => {
    for (let i = series.length - 1; i >= 0; i--) if (!series[i].partial && series[i].count > 0) return i;
    return series.length - 1;
  }, [series]);
  const [selected, setSelected] = useState(lastComplete);
  const [wrapRef, width] = useWidth<HTMLDivElement>();

  const momentIndex = useMemo(() => {
    const m = new Map<number, Moment[]>();
    data.moments.forEach(mo => {
      const i = series.findIndex(b => mo.start >= b.start && mo.start <= b.end);
      if (i >= 0) m.set(i, [...(m.get(i) ?? []), mo]);
    });
    return m;
  }, [data.moments, series]);

  const values = series.map(b => b[metric]);
  const yMax = niceMax(Math.max(...values, 1));
  const innerW = Math.max(width - PAD.left - PAD.right, 10);
  const innerH = H - PAD.top - PAD.bottom;
  const step = innerW / Math.max(series.length, 1);
  const gap = step >= 6 ? 2 : step >= 3 ? 1 : 0;
  const y = (v: number) => PAD.top + innerH - (v / yMax) * innerH;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map(f => f * yMax);

  // X labels: months for daily data, quarters (or years when crowded) for weekly
  const xLabels = useMemo(() => {
    const out: { i: number; text: string }[] = [];
    let lastKey = '';
    const crowded = innerW / Math.max(series.length, 1) < 3;
    series.forEach((b, i) => {
      const d = new Date(`${b.start}T12:00:00+08:00`);
      const key = bucket === 'day'
        ? `${d.getUTCFullYear()}-${Math.floor((d.getUTCDate() - 1) / 7)}-${d.getUTCMonth()}`
        : crowded ? `${d.getUTCFullYear()}` : `${d.getUTCFullYear()}-${Math.floor(d.getUTCMonth() / 3)}`;
      if (key !== lastKey) {
        lastKey = key;
        if (bucket === 'day' && d.getUTCDay() !== 1 && i !== 0) return;
        out.push({
          i,
          text: bucket === 'day'
            ? fmtDay(b.start, { day: 'numeric', month: 'short' })
            : crowded ? fmtDay(b.start, { year: 'numeric' }) : fmtDay(b.start, { month: 'short', year: '2-digit' }),
        });
      }
    });
    const minGap = 56 / step;
    return out.filter((l, k) => k === 0 || l.i - out[k - 1].i >= minGap);
  }, [series, bucket, step, innerW]);

  const active = hover ?? selected;
  const sel = series[selected];
  const tip = hover !== null ? series[hover] : null;
  const tipX = hover !== null ? PAD.left + step * (hover + 0.5) : 0;

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowLeft') { e.preventDefault(); setSelected(s => Math.max(0, s - 1)); }
    if (e.key === 'ArrowRight') { e.preventDefault(); setSelected(s => Math.min(series.length - 1, s + 1)); }
    if (e.key === 'Home') { e.preventDefault(); setSelected(0); }
    if (e.key === 'End') { e.preventDefault(); setSelected(series.length - 1); }
  };

  if (!series.length) {
    return <p className="text-[0.88rem] py-8 text-center" style={{ color: 'var(--text-muted)' }}>No posts in this window.</p>;
  }

  const unit = METRICS.find(m => m.key === metric)!.unit;
  const anyProvisional = metric === 'avg_score' && series.some(b => b.provisional);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <div role="group" aria-label="Metric" className="inline-flex p-0.5 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-alt)' }}>
          {METRICS.map(m => (
            <button
              key={m.key}
              type="button"
              aria-pressed={metric === m.key}
              onClick={() => setMetric(m.key)}
              className="px-3 py-1 pointer-coarse:min-h-10 rounded-md text-[0.8rem] font-medium cursor-pointer transition-colors"
              style={metric === m.key
                ? { background: 'var(--surface)', color: 'var(--text-1)', boxShadow: 'var(--shadow-1), 0 0 0 1px var(--border)' }
                : { color: 'var(--text-3)' }}
            >
              {m.label}
            </button>
          ))}
        </div>
        <p className="text-[0.76rem] m-0 flex flex-wrap items-center gap-x-3 gap-y-1" style={{ color: 'var(--text-muted)' }}>
          <span>Per {bucket === 'day' ? 'day' : 'week'}, Singapore time. Click a bar to see what was posted.</span>
          {data.moments.length > 0 && (
            <span className="inline-flex items-center gap-1.5">
              <svg width="10" height="10" aria-hidden="true"><circle cx="5" cy="5" r="3.5" fill="var(--surface)" stroke="var(--orange)" strokeWidth="2" /></svg>
              moment
            </span>
          )}
          {(anyProvisional || series.some(b => b.partial)) && (
            <span className="inline-flex items-center gap-1.5">
              <svg width="12" height="10" aria-hidden="true"><rect width="12" height="10" rx="2" fill="url(#hatch-key)" /><defs><pattern id="hatch-key" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="4" height="4" fill="var(--blue-light)" /><rect width="2" height="4" fill="var(--blue)" opacity="0.55" /></pattern></defs></svg>
              {anyProvisional ? 'still collecting reactions' : 'week in progress'}
            </span>
          )}
        </p>
      </div>

      <div ref={wrapRef} className="relative select-none">
        <svg
          width={width}
          height={H}
          role="img"
          tabIndex={0}
          onKeyDown={onKey}
          aria-label={`${unit} per ${bucket}, ${bucketLabel(series[0], bucket)} to ${bucketLabel(series[series.length - 1], bucket)}. Selected: ${bucketLabel(sel, bucket)}, ${sel[metric]} ${unit}. Use arrow keys to move.`}
          className="block rounded-md outline-offset-4"
          onMouseLeave={() => setHover(null)}
        >
          <defs>
            <pattern id="hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="5" height="5" fill="var(--blue-light)" />
              <rect width="2" height="5" fill="var(--blue)" opacity="0.55" />
            </pattern>
          </defs>

          {ticks.map(t => (
            <g key={t}>
              <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} stroke="var(--border)" strokeDasharray={t === 0 ? undefined : '2 4'} />
              <text x={PAD.left - 8} y={y(t)} dy="0.32em" textAnchor="end" fontSize="11" fill="var(--text-muted)" style={{ fontFamily: 'var(--font-mono)' }}>
                {t >= 1000 ? `${(t / 1000).toFixed(t % 1000 ? 1 : 0)}k` : Math.round(t)}
              </text>
            </g>
          ))}

          {series.map((b, i) => {
            const v = b[metric];
            const x = PAD.left + step * i + gap / 2;
            const w = Math.max(step - gap, 1);
            const top = y(v);
            const dim = metric === 'avg_score' ? b.provisional : b.partial;
            const isActive = i === active;
            return (
              <path
                key={b.start}
                d={barPath(x, top, w, PAD.top + innerH - top)}
                fill={dim ? 'url(#hatch)' : 'var(--blue)'}
                opacity={isActive || dim ? 1 : hover !== null || selected !== null ? 0.55 : 1}
              />
            );
          })}

          {/* Selection marker under the axis */}
          <rect x={PAD.left + step * selected} y={PAD.top + innerH + 1} width={Math.max(step, 2)} height={3} rx={1.5} fill="var(--text-1)" />

          {[...momentIndex.keys()].map(i => (
            <circle key={i} cx={PAD.left + step * (i + 0.5)} cy={PAD.top - 9} r={4} fill="var(--surface)" stroke="var(--orange)" strokeWidth={2} />
          ))}

          {xLabels.map(l => (
            <text key={l.i} x={PAD.left + step * l.i} y={H - 6} fontSize="11" fill="var(--text-muted)" style={{ fontFamily: 'var(--font-mono)' }}>
              {l.text}
            </text>
          ))}

          {hover !== null && (
            <line x1={tipX} x2={tipX} y1={PAD.top - 2} y2={PAD.top + innerH} stroke="var(--text-muted)" strokeWidth={1} strokeDasharray="2 3" />
          )}

          {/* Hit targets: full-height columns, wider than the bars */}
          {series.map((b, i) => (
            <rect
              key={`hit-${b.start}`}
              x={PAD.left + step * i}
              y={0}
              width={step}
              height={H - PAD.bottom}
              fill="transparent"
              className="cursor-pointer"
              onMouseEnter={() => setHover(i)}
              onClick={() => setSelected(i)}
            />
          ))}
        </svg>

        {tip && (
          <div
            className="pointer-events-none absolute z-10 w-60 rounded-lg border px-3 py-2.5 text-[0.76rem] leading-snug"
            style={{
              left: tipX + 252 > width ? tipX - 252 : tipX + 12,
              top: PAD.top + 4,
              background: 'var(--surface)',
              borderColor: 'var(--border)',
              boxShadow: 'var(--shadow-2)',
              color: 'var(--text-2)',
            }}
          >
            <div className="font-semibold mb-1" style={{ color: 'var(--text-1)' }}>{bucketLabel(tip, bucket)}</div>
            <div className="flex justify-between tabular-nums"><span>Posts</span><span style={{ color: 'var(--text-1)' }}>{tip.count.toLocaleString()}{tip.partial ? ' so far' : ''}</span></div>
            <div className="flex justify-between tabular-nums"><span>Avg score</span><span style={{ color: 'var(--text-1)' }}>{tip.avg_score}{tip.provisional ? ' (rising)' : ''}</span></div>
            {tip.top[0] && <div className="mt-1.5 pt-1.5 border-t line-clamp-2" style={{ borderColor: 'var(--border)', color: 'var(--text-3)' }}>&ldquo;{tip.top[0].excerpt}&rdquo;</div>}
          </div>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.85fr)] mt-6">
        <BucketDetail b={sel} kind={bucket} />
        <Moments moments={data.moments} kind={bucket} onPick={start => {
          const i = series.findIndex(b => start >= b.start && start <= b.end);
          if (i >= 0) setSelected(i);
        }} selectedStart={sel.start} selectedEnd={sel.end} />
      </div>

      <details className="mt-5 text-[0.8rem]" style={{ color: 'var(--text-3)' }}>
        <summary className="cursor-pointer w-fit py-1" style={{ color: 'var(--text-muted)' }}>View as table</summary>
        <div className="max-h-72 overflow-auto mt-2 rounded-lg border" style={{ borderColor: 'var(--border)' }}>
          <table className="w-full text-left tabular-nums">
            <thead className="sticky top-0" style={{ background: 'var(--surface-alt)' }}>
              <tr><th className="px-3 py-1.5 font-medium">{bucket === 'day' ? 'Day' : 'Week of'}</th><th className="px-3 py-1.5 font-medium text-right">Posts</th><th className="px-3 py-1.5 font-medium text-right">Avg score</th></tr>
            </thead>
            <tbody>
              {[...series].reverse().map(b => (
                <tr key={b.start} className="border-t" style={{ borderColor: 'var(--border-light)' }}>
                  <td className="px-3 py-1">{b.start}</td>
                  <td className="px-3 py-1 text-right">{b.count}{b.partial ? '*' : ''}</td>
                  <td className="px-3 py-1 text-right">{b.avg_score}{b.provisional ? '*' : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

function PostLine({ p, rank }: { p: Timeline['series'][number]['top'][number]; rank?: number }) {
  return (
    <Link href={`/post/${p.id}`} className="list-row flex gap-3 px-2.5 py-2.5 -mx-2.5 rounded-lg no-underline" style={{ color: 'var(--text-1)' }}>
      {rank !== undefined && (
        <span className="text-[0.75rem] w-4 shrink-0 pt-0.5 text-right tabular-nums" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{rank}</span>
      )}
      <span className="flex-1 min-w-0">
        <span className="block text-[0.86rem] leading-snug line-clamp-2 text-pretty">{p.excerpt}</span>
        <span className="mt-1 flex gap-3 text-[0.72rem] tabular-nums" style={{ color: 'var(--text-muted)' }}>
          <span className="inline-flex items-center gap-1"><HeartIcon />{p.reactions}<span className="sr-only"> reactions</span></span>
          <span className="inline-flex items-center gap-1"><ReplyIcon />{p.replies}<span className="sr-only"> replies</span></span>
          <span>score {p.score.toLocaleString()}</span>
        </span>
      </span>
    </Link>
  );
}

function BucketDetail({ b, kind }: { b: TimelineBucket; kind: Timeline['bucket'] }) {
  return (
    <div aria-live="polite">
      <div className="flex items-baseline justify-between gap-3 mb-1">
        <h3 className="text-[0.95rem] font-semibold tracking-[-0.01em] m-0">{bucketLabel(b, kind)}</h3>
        <span className="text-[0.76rem] tabular-nums shrink-0" style={{ color: 'var(--text-muted)' }}>
          {b.count.toLocaleString()} posts{b.partial ? ' so far' : ''} · avg {b.avg_score}
        </span>
      </div>
      {b.top.length === 0 ? (
        <p className="text-[0.85rem] py-4" style={{ color: 'var(--text-muted)' }}>Nothing was posted.</p>
      ) : (
        <>
          <div className="mt-2">{b.top.map((p, i) => <PostLine key={p.id} p={p} rank={i + 1} />)}</div>
          <Link href={feedHref(b.start, b.end)} className="inline-flex items-center gap-1 mt-2 text-[0.82rem] font-medium no-underline hover:underline underline-offset-4" style={{ color: 'var(--blue)' }}>
            Browse all {b.count.toLocaleString()} posts from {kind === 'day' ? 'this day' : 'this week'} <span aria-hidden="true">→</span>
          </Link>
        </>
      )}
    </div>
  );
}

function Moments({ moments, kind, onPick, selectedStart, selectedEnd }: {
  moments: Moment[]; kind: Timeline['bucket']; onPick: (start: string) => void; selectedStart: string; selectedEnd: string;
}) {
  if (!moments.length) return null;
  return (
    <div>
      <h3 className="text-[0.95rem] font-semibold tracking-[-0.01em] m-0 mb-2">Moments in this window</h3>
      <ol className="m-0 p-0 list-none">
        {moments.map(m => {
          const inSel = m.start >= selectedStart && m.start <= selectedEnd;
          return (
            <li key={`${m.kind}-${m.start}-${m.post?.id}`}>
              <button
                type="button"
                onClick={() => onPick(m.start)}
                aria-pressed={inSel}
                className="w-full text-left flex gap-3 px-2.5 py-2 -mx-2.5 rounded-lg cursor-pointer transition-colors hover:bg-[var(--surface-alt)]"
                style={inSel ? { background: 'var(--surface-alt)' } : undefined}
              >
                <span className="w-[4.5rem] shrink-0 text-[0.74rem] tabular-nums pt-0.5" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  {fmtDay(m.start, { day: 'numeric', month: 'short' })}<br />{fmtDay(m.start, { year: 'numeric' })}
                </span>
                <span className="flex-1 min-w-0">
                  <span className="block text-[0.74rem] font-medium" style={{ color: 'var(--orange)' }}>
                    {m.kind === 'spike'
                      ? `Busy ${kind} · ${m.ratio}× the usual volume`
                      : `Most-engaged post · score ${m.post?.score.toLocaleString()}`}
                  </span>
                  {m.post && <span className="block text-[0.84rem] leading-snug line-clamp-2 mt-0.5" style={{ color: 'var(--text-1)' }}>{m.post.excerpt}</span>}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
