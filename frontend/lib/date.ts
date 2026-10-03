const SGT = 'Asia/Singapore';

export function formatShortDate(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00+08:00` : iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString('en-SG', { timeZone: SGT, day: 'numeric', month: 'short', year: 'numeric' });
}

export function formatConfessionDate(iso: string): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const date = d.toLocaleDateString('en-SG', { timeZone: SGT, day: 'numeric', month: 'short' });
    const time = d.toLocaleTimeString('en-SG', { timeZone: SGT, hour: '2-digit', minute: '2-digit', hour12: false });
    return `${date} · ${time}`;
  } catch {
    return iso.slice(0, 16);
  }
}

// "2:47am" if the confession was sent between midnight and 5am SGT, else null
export function smallHoursTime(iso: string): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const h = Number(d.toLocaleString('en-SG', { timeZone: SGT, hour: 'numeric', hourCycle: 'h23' }));
  if (h >= 5) return null;
  return d
    .toLocaleTimeString('en-SG', { timeZone: SGT, hour: 'numeric', minute: '2-digit', hour12: true })
    .replace(/\s/g, '')
    .toLowerCase();
}
