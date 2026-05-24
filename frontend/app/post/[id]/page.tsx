export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

import { notFound } from 'next/navigation';
import Link from 'next/link';
import type { Metadata } from 'next';
import { Nav } from '@/components/Nav';
import { ReplyCard } from '@/components/ReplyCard';
import { getPost } from '@/lib/api';
import { formatConfessionDate } from '@/lib/date';
import { tgMdToHtml } from '@/lib/markdown';

interface Props {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const data = await getPost(parseInt(id, 10));
  const title = data?.post.title || `Confession #${id}`;
  return { title: `${title} — NUSConfessIT` };
}

export default async function PostPage({ params }: Props) {
  const { id } = await params;
  const data = await getPost(parseInt(id, 10));
  if (!data) notFound();

  const { post, replies, total } = data;
  const tgUrl = `https://t.me/NUSConfessIT/${id}`;
  const html = tgMdToHtml(post.content ?? '');

  return (
    <>
      <Nav />

      <main className="max-w-5xl mx-auto px-3 md:px-4 pb-12 md:pb-16 pt-4 md:pt-6">
        <div className="flex gap-3 md:gap-4 flex-wrap items-center mb-4 text-[0.8rem]" style={{ color: 'var(--text-3)' }}>
          <Link href="/" className="no-underline font-medium hover:opacity-70 transition-opacity" style={{ color: 'var(--text-2)' }}>
            ← All Posts
          </Link>
          <span style={{ color: 'var(--border)' }}>·</span>
          <span>{formatConfessionDate(post.date || '')}</span>
          <span>❤️ <strong style={{ color: 'var(--text-2)' }}>{post.reactions_count}</strong></span>
          {post.reply_count > 0 && <span>💬 <strong style={{ color: 'var(--text-2)' }}>{post.reply_count}</strong></span>}
          <a href={tgUrl} target="_blank" rel="noopener noreferrer"
             className="no-underline hover:opacity-70 transition-opacity ml-auto" style={{ color: 'var(--text-muted)' }}>
            Telegram ↗
          </a>
        </div>

        {post.title && (
          <h1 className="text-lg md:text-xl font-bold leading-snug mb-4"
              style={{ color: 'var(--text-1)', fontFamily: 'var(--font-display)' }}>
            {post.title}
          </h1>
        )}

        <div className="reading-zone reading-zone-entry rounded-xl p-4 md:p-6 shadow-sm mb-5 md:mb-7 text-[0.95rem] md:text-[1rem] leading-[1.75] md:leading-[1.85]"
             style={{ background: 'var(--surface)', color: 'var(--text-1)' }}
             dangerouslySetInnerHTML={{ __html: html }} />

        {replies.length > 0 ? (
          <section>
            <h2 className="text-[0.72rem] font-semibold uppercase tracking-widest mb-4"
                style={{ color: 'var(--text-muted)' }}>
              Discussion ({replies.length})
            </h2>
            {replies.map((r: any, i: number) => (
              <ReplyCard key={r.id || -i} reply={{
                id: r.id || -i,
                date: r.date || '',
                text: r.body || '',
                content: r.body || null,
                author: null,
                reactions_count: null,
                reactions_up: null,
                reactions_down: null,
                post_id: parseInt(id, 10),
              }} index={i} />
            ))}
          </section>
        ) : (
          <div className="rounded-xl p-5 shadow-sm text-center" style={{ background: 'var(--surface)' }}>
            <p className="text-[0.92rem] py-4" style={{ color: 'var(--text-muted)' }}>
              No discussion captured — the full thread is on{' '}
              <a href={tgUrl} target="_blank" rel="noopener noreferrer"
                 className="font-semibold" style={{ color: 'var(--blue)' }}>Telegram</a>.
            </p>
          </div>
        )}
      </main>
    </>
  );
}