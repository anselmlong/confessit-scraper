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
  if (!msg) return null;
  return <p className="text-white/50 text-xs mt-1 italic">{msg}</p>;
}
