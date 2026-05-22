import Link from 'next/link';
import { ThemeToggle } from './ThemeToggle';

export function Nav({ activePage = '' }: { activePage?: string }) {
  return (
    <nav
      className="sticky top-0 z-50 flex items-center gap-0 px-6 shadow-[0_2px_8px_rgba(0,0,0,0.22)]"
      style={{ background: '#003D7C' }}
    >
      <Link
        href="/"
        className="text-white font-black text-[1rem] py-[14px] pr-6 border-r border-white/15 mr-2
                   tracking-tight select-none no-underline hover:opacity-90 transition-opacity"
        style={{ textDecoration: 'none' }}
      >
        NUSConfessIT <span style={{ color: '#EF7C00' }}>Dashboard</span>
      </Link>

      <Link
        href="/"
        className={`text-[0.88rem] font-medium px-4 py-[14px] no-underline transition-colors
          ${activePage === 'home'
            ? 'text-white border-b-[3px] border-[#EF7C00]'
            : 'text-white/75 hover:text-white'}`}
      >
        Overview
      </Link>

      <Link
        href="/stats"
        className={`text-[0.88rem] font-medium px-4 py-[14px] no-underline transition-colors
          ${activePage === 'stats'
            ? 'text-white border-b-[3px] border-[#EF7C00]'
            : 'text-white/75 hover:text-white'}`}
      >
        Stats
      </Link>

      <span className="flex-1" />
      <ThemeToggle />
    </nav>
  );
}
