'use client';

import { useTheme } from 'next-themes';
import { useEffect, useState } from 'react';

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted) return <div className="w-[34px] h-[34px]" />;

  return (
    <button
      onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
      aria-label="Toggle dark mode"
      className="w-[34px] h-[34px] rounded-full flex items-center justify-center text-base
                 bg-white/10 border border-white/20 text-white/85 cursor-pointer
                 hover:bg-white/20 transition-all duration-200 hover:rotate-[22deg]"
    >
      {theme === 'dark' ? '☀️' : '🌙'}
    </button>
  );
}
