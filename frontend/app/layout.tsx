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
          href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
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
