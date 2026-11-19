import Link from 'next/link';
import { ThemeToggle } from './ThemeToggle';

const LINKS = [
  { key: 'home', href: '/', label: 'Confessions' },
  { key: 'stats', href: '/stats', label: 'Trends & stats' },
];

export function Nav({ activePage = '' }: { activePage?: string }) {
  return (
    <nav
      aria-label="Main"
      className="sticky top-0 z-50 border-b backdrop-blur-md backdrop-saturate-150"
      style={{ background: 'var(--nav-bg)', borderColor: 'var(--border)' }}
    >
      <div className="max-w-5xl mx-auto flex items-center gap-1 px-3 md:px-4 h-14">
        <Link
          href="/"
          className="flex items-center gap-2 mr-3 md:mr-5 no-underline font-semibold text-[0.95rem] tracking-[-0.02em] select-none"
          style={{ color: 'var(--text-1)' }}
        >
          <svg aria-hidden="true" width="22" height="22" viewBox="0 0 64 64">
            <rect width="64" height="64" rx="16" fill="var(--fill)" />
            <path d="M42 22.5a14 14 0 1 0 0 19" fill="none" stroke="#fff" strokeWidth="7" strokeLinecap="round" />
          </svg>
          <span>confessit<span style={{ color: 'var(--text-muted)' }}>.space</span></span>
        </Link>

        {LINKS.map(l => (
          <Link
            key={l.key}
            href={l.href}
            aria-current={activePage === l.key ? 'page' : undefined}
            className={`text-[0.84rem] font-medium px-2.5 md:px-3 py-1.5 rounded-md no-underline whitespace-nowrap transition-colors
              ${activePage === l.key
                ? 'text-[var(--text-1)] bg-[var(--surface-alt)]'
                : 'text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-[var(--surface-alt)]'}`}
          >
            {l.label}
          </Link>
        ))}

        <span className="flex-1" />
        <ThemeToggle />
      </div>
    </nav>
  );
}
