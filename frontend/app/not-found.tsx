import Link from 'next/link';
import { Nav } from '@/components/Nav';

export default function NotFound() {
  return (
    <>
      <Nav />
      <main className="max-w-5xl mx-auto px-4 pt-24 pb-16 text-center">
        <h1 className="text-6xl font-black mb-4" style={{ color: 'var(--blue)' }}>
          404
        </h1>
        <p className="text-lg mb-8" style={{ color: 'var(--text-2)' }}>
          This confession doesn&apos;t exist — or hasn&apos;t been said yet.
        </p>
        <Link
          href="/"
          className="no-underline font-semibold px-6 py-3 rounded-xl text-white
                     transition-all hover:-translate-y-0.5 inline-block"
          style={{ background: 'var(--blue)' }}
        >
          ← Back to Overview
        </Link>
      </main>
    </>
  );
}
