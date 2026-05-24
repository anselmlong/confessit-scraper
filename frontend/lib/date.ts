const SGT = 'Asia/Singapore';

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
