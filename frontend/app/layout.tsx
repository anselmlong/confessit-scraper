import type { Metadata, Viewport } from 'next';
import { ThemeProvider } from '@/components/ThemeProvider';
import './globals.css';

export const metadata: Metadata = {
  title: 'NUSConfessIT Dashboard',
  description: 'Browse, search, and explore confessions from the NUSConfessIT Telegram channel.',
  icons: { icon: '/favicon.svg' },
};

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#fafafa' },
    { media: '(prefers-color-scheme: dark)', color: '#09090b' },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <script dangerouslySetInnerHTML={{ __html: `
          console.log('%c confessit ', 'background:#09090b;color:#8b93f8;font-family:monospace;font-size:13px;padding:2px 6px;border-radius:3px;');
          console.log('%c scraped from telegram. built out of curiosity. ', 'color:#8e8e98;font-size:11px;font-family:monospace;');
        `}} />
        <ThemeProvider>
          {children}
          <footer className="max-w-5xl mx-auto mt-4 px-4 py-8 text-center text-xs border-t" style={{ color: 'var(--text-muted)', borderColor: 'var(--border)' }}>
            NUSConfessIT Dashboard &middot; Data from{' '}
            <a
              href="https://t.me/NUSConfessIT"
              className="inline-block px-1 py-2 pointer-coarse:py-3.5"
              style={{ color: 'var(--blue)' }}
            >
              t.me/NUSConfessIT
            </a>
            {' '}&middot;{' '}
            <a href="/launch.mp4" className="inline-block px-1 py-2 pointer-coarse:py-3.5" style={{ color: 'var(--blue)' }}>
              20-second tour
            </a>
            {' '}&middot;{' '}
            <a
              href="https://ko-fi.com/anselmlong"
              target="_blank"
              rel="noopener"
              className="inline-block px-1 py-2 pointer-coarse:py-3.5"
              style={{ color: 'var(--blue)' }}
            >
              &#9749; support me on Ko-fi
            </a>
            <br />
            Content is mirrored from a public Telegram channel. For removal requests, contact{' '}
            <a
              href="mailto:anselmpius@gmail.com"
              className="inline-block px-1 py-2 pointer-coarse:py-3.5"
              style={{ color: 'var(--blue)' }}
            >
              anselmpius@gmail.com
            </a>
          </footer>
        </ThemeProvider>
      </body>
    </html>
  );
}
