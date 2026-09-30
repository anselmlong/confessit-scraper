'use client';

import { useEffect, useState } from 'react';

// The channel's own "Time Reminder" copypasta, waiting at the bottom of the scroll
function reminder(now: Date): string {
  const h = now.getHours();
  const time = now
    .toLocaleTimeString('en-SG', { hour: 'numeric', minute: '2-digit', hour12: true })
    .replace(/\s/g, '')
    .toLowerCase();
  return h < 5 ? `time now is ${time}, go to sleep` : `time now is ${time}`;
}

export function EndOfList({ count }: { count: number }) {
  const [msg, setMsg] = useState('');
  useEffect(() => setMsg(reminder(new Date())), []);

  return (
    <div className="end-of-list flex items-center gap-3 mt-8 mb-2 text-[0.78rem]" style={{ color: 'var(--text-muted)' }}>
      <span className="flex-1 h-px" aria-hidden="true" style={{ background: 'var(--border)' }} />
      <p className="text-center m-0">
        That&apos;s all {count}.
        {/* Height reserved before hydration so nothing shifts */}
        <span className="block italic min-h-[1.3em]">{msg}</span>
      </p>
      <span className="flex-1 h-px" aria-hidden="true" style={{ background: 'var(--border)' }} />
    </div>
  );
}
