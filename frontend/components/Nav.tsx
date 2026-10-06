import Link from 'next/link';
import { ThemeToggle } from './ThemeToggle';

export function Nav({ activePage = '' }: { activePage?: string }) {
  return (
    <nav
      aria-label="Main"
      className="sticky top-0 z-50 flex items-center gap-0 px-3 md:px-6 shadow-[0_2px_8px_rgba(0,0,0,0.22)]"
      style={{ background: 'var(--nav-bg)' }}
    >
      <Link
        href="/"
        className="text-white font-black text-[0.85rem] md:text-[1rem] py-[10px] md:py-[14px] pr-3 md:pr-6 border-r border-white/15 mr-1 md:mr-2
                   tracking-tight select-none no-underline hover:opacity-90 transition-opacity"
        style={{ textDecoration: 'none', fontFamily: 'var(--font-display)' }}
      >
        <span className="hidden sm:inline">NUSConfessIT </span><span className="sm:hidden">NC </span><span style={{ color: '#d9a03a' }}>Dashboard</span>
      </Link>

      <Link
        href="/"
        aria-current={activePage === 'home' ? 'page' : undefined}
        className={`text-[0.8rem] md:text-[0.88rem] font-medium px-2 md:px-4 py-[10px] md:py-[14px] no-underline transition-colors
          ${activePage === 'home'
            ? 'text-white shadow-[inset_0_-3px_0_var(--blue)]'
            : 'text-white/75 hover:text-white'}`}
      >
        Overview
      </Link>

      <Link
        href="/stats"
        aria-current={activePage === 'stats' ? 'page' : undefined}
        className={`text-[0.8rem] md:text-[0.88rem] font-medium px-2 md:px-4 py-[10px] md:py-[14px] no-underline transition-colors
          ${activePage === 'stats'
            ? 'text-white shadow-[inset_0_-3px_0_var(--blue)]'
            : 'text-white/75 hover:text-white'}`}
      >
        Stats
      </Link>

      <span className="flex-1" />
      <ThemeToggle />
    </nav>
  );
}
