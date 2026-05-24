import type { Metadata } from 'next';
import { ThemeProvider } from '@/components/ThemeProvider';
import './globals.css';

export const metadata: Metadata = {
  title: 'NUSConfessIT Dashboard',
  description: 'Browse, search, and explore confessions from the NUSConfessIT Telegram channel.',
  icons: { icon: '/favicon.svg' },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,500;12..96,700;12..96,800&family=Libre+Franklin:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <script dangerouslySetInnerHTML={{ __html: `
          console.log('%c confessit ', 'background:#0d1520;color:#4d8fd6;font-family:monospace;font-size:13px;padding:2px 6px;border-radius:3px;');
          console.log('%c scraped from telegram. built out of curiosity. ', 'color:#445568;font-size:11px;font-family:monospace;');
        `}} />
        <ThemeProvider>
          {children}
          <footer className="text-center py-6 text-xs" style={{ color: 'var(--text-muted)' }}>
            NUSConfessIT Dashboard &middot; Data from{' '}
            <a
              href="https://t.me/NUSConfessIT"
              className="inline-block px-1 py-2"
              style={{ color: 'var(--blue)' }}
            >
              t.me/NUSConfessIT
            </a>
          </footer>
        </ThemeProvider>
      </body>
    </html>
  );
}
