'use client';

import { useEffect, useRef, useState } from 'react';

/** Track an element's content width so SVG charts draw at real pixels (text never stretches). */
export function useWidth<T extends HTMLElement>(fallback = 640) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

export function niceMax(v: number): number {
  if (v <= 0) return 1;
  const exp = 10 ** Math.floor(Math.log10(v));
  const f = v / exp;
  const step = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
  return step * exp;
}

const SGT = 'Asia/Singapore';
export function fmtDay(iso: string, opts: Intl.DateTimeFormatOptions) {
  return new Date(`${iso.length === 7 ? `${iso}-01` : iso}T12:00:00+08:00`).toLocaleDateString('en-SG', { timeZone: SGT, ...opts });
}
