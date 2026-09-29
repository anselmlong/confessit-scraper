'use client';

import { useEffect, useState } from 'react';

const TAGLINES: [number, string][] = [
  [4,  "Still awake? You're in good company."],
  [8,  "Early start — or you never stopped."],
  [12, "Good morning. Here's what's been said."],
  [17, "Afternoon procrastination. Fully supported."],
  [21, "Evening edition — catch up on campus."],
  [24, "Late night. The best stuff comes out after dark."],
];

export function TimeTagline() {
  const [msg, setMsg] = useState('');
  useEffect(() => {
    const h = new Date().getHours();
    const entry = TAGLINES.find(([max]) => h < max);
    setMsg(entry ? entry[1] : TAGLINES[TAGLINES.length - 1][1]);
  }, []);
  // Reserve the line before hydration so the filter bar doesn't jump
  return (
    <p className="time-tagline text-[0.8rem] italic min-h-[1.3rem] mb-2 md:mb-3 px-1" style={{ color: 'var(--text-3)' }}>
      {msg}
    </p>
  );
}
