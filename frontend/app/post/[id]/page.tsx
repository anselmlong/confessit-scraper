export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

import { notFound } from 'next/navigation';
import Link from 'next/link';
import type { Metadata } from 'next';
import { Nav } from '@/components/Nav';
import { ReplyCard } from '@/components/ReplyCard';
import { getPost } from '@/lib/api';
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
      <header className="text-white px-4 md:px-6 py-5 md:py-8" style={{ background: 'linear-gradient(135deg, #003D7C 0%, #00509E 100%)' }}>
        <div className="flex gap-3 md:gap-5 mb-2.5 md:mb-3.5 items-center flex-wrap">
          <Link href="/" className="text-white/65 no-underline text-[0.8rem] md:text-[0.84rem] font-medium hover:text-white transition-colors">
            ← All Posts
          </Link>
          <a href={tgUrl} target="_blank" rel="noopener noreferrer"
             className="text-white/65 no-underline text-[0.8rem] md:text-[0.84rem] font-medium hover:text-white transition-colors">
            View on Telegram ↗
          </a>
        </div>
        <h1 className="text-lg md:text-2xl font-bold leading-snug">{post.title || `Confession #${id}`}</h1>
        <p className="text-white/75 mt-1 text-sm">
          {(post.date || '').slice(0, 16).replace('T', ' ')} &middot; #{id}
        </p>
      </header>

      <main className="max-w-5xl mx-auto px-3 md:px-4 pb-12 md:pb-16 pt-4 md:pt-6">
        <div className="flex gap-3 md:gap-5 flex-wrap items-center mb-4 md:mb-5 text-[0.85rem] md:text-[0.88rem]" style={{ color: 'var(--text-3)' }}>
          <span>❤️ <strong style={{ color: 'var(--text-1)' }}>{post.reactions_count}</strong></span>
          <span>💬 <strong style={{ color: 'var(--text-1)' }}>{post.reply_count}</strong></span>
          <span>↗ <strong style={{ color: 'var(--text-1)' }}>{post.forwards}</strong></span>
        </div>

        <div className="reading-zone rounded-xl p-4 md:p-6 shadow-sm mb-5 md:mb-7 text-[0.95rem] md:text-[1rem] leading-[1.75] md:leading-[1.85]"
             style={{ background: 'var(--surface)', color: 'var(--text-1)' }}
             dangerouslySetInnerHTML={{ __html: html }} />

        {replies.length > 0 ? (
          <section>
            <h2 className="text-[0.85rem] font-bold uppercase tracking-[0.8px] pb-2 border-b-2 inline-block m-0 mb-4"
                style={{ color: 'var(--blue)', borderColor: 'var(--orange)' }}>
              💬 Discussion ({replies.length})
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