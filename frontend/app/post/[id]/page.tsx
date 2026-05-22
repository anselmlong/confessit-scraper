export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

import { notFound } from 'next/navigation';
import Link from 'next/link';
import type { Metadata } from 'next';
import { Nav } from '@/components/Nav';
import { ReplyCard } from '@/components/ReplyCard';
import { getPost, getReplies, getTotalInGroup } from '@/lib/db';
import type { Post, Reply } from '@/lib/types';
import { tgMdToHtml } from '@/lib/markdown';

const API_BASE = process.env.NEXT_PUBLIC_VPS_API || '';

async function fetchPostFromVPS(id: number) {
  if (!API_BASE) return null;
  try {
    const r = await fetch(`${API_BASE}/api/post/${id}`, { next: { revalidate: 300 } });
    if (!r.ok) return null;
    return r.json();
  } catch { return null; }
}

interface Props {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const postId = parseInt(id, 10);
  const vps = await fetchPostFromVPS(postId);
  if (vps?.post?.title) return { title: `${vps.post.title} — NUSConfessIT` };
  const post = getPost(postId);
  if (!post) return { title: 'Not Found — NUSConfessIT' };
  const label = post.confession_id ? `#${post.confession_id}` : `ID ${post.id}`;
  return { title: `${post.title ?? `Confession ${label}`} — NUSConfessIT` };
}

export default async function PostPage({ params }: Props) {
  const { id } = await params;
  const postId = parseInt(id, 10);

  // Try VPS API first
  const vps = await fetchPostFromVPS(postId);
  if (vps?.post) {
    const p = vps.post;
    const replies: Reply[] = (vps.replies || []).map((r: any, i: number) => ({
      id: r.id || -i,
      date: r.date || '',
      text: r.body || '',
      content: r.body || null,
      author: null,
      reactions_count: null,
      reactions_up: null,
      reactions_down: null,
      post_id: postId,
    }));

    return (
      <>
        <Nav />
        <header
          className="text-white px-6 py-8"
          style={{ background: 'linear-gradient(135deg, #003D7C 0%, #00509E 100%)' }}
        >
          <div className="flex gap-5 mb-3.5 items-center flex-wrap">
            <Link href="/" className="text-white/65 no-underline text-[0.84rem] font-medium hover:text-white transition-colors">
              ← All Posts
            </Link>
            <a href={`https://t.me/NUSConfessIT/${postId}`} target="_blank" rel="noopener noreferrer"
               className="text-white/65 no-underline text-[0.84rem] font-medium hover:text-white transition-colors">
              View on Telegram ↗
            </a>
          </div>
          <h1 className="text-2xl font-bold">{p.title || `Confession ID ${postId}`}</h1>
          <p className="text-white/75 mt-1.5 text-sm">
            {(p.date ?? '').slice(0, 10)} &middot; #{postId}
            {p.category && p.category !== 'Others' && ` · ${p.category}`}
          </p>
        </header>
        <main className="max-w-5xl mx-auto px-4 pb-16 pt-6">
          <div className="flex gap-5 flex-wrap items-center mb-5 text-[0.88rem]" style={{ color: 'var(--text-3)' }}>
            <span>❤️ <strong style={{ color: 'var(--text-1)' }}>{p.reactions}</strong></span>
            <span>💬 <strong style={{ color: 'var(--text-1)' }}>{p.replies}</strong></span>
            <span>↗ <strong style={{ color: 'var(--text-1)' }}>{p.forwards ?? 0}</strong></span>
          </div>
          <div className="reading-zone rounded-xl p-6 shadow-sm mb-7 text-[1rem] leading-[1.85]"
               style={{ background: 'var(--surface)', color: 'var(--text-1)' }}
               dangerouslySetInnerHTML={{ __html: tgMdToHtml(p.body || '') }} />
          {replies.length > 0 ? (
            <section>
              <h2 className="text-[0.85rem] font-bold uppercase tracking-[0.8px] pb-2 border-b-2 inline-block m-0 mb-4"
                  style={{ color: 'var(--blue)', borderColor: 'var(--orange)' }}>
                💬 Discussion ({replies.length})
              </h2>
              {replies.map((r, i) => (<ReplyCard key={r.id} reply={r} index={i} />))}
            </section>
          ) : (
            <div className="rounded-xl p-5 shadow-sm text-center" style={{ background: 'var(--surface)' }}>
              <p className="text-[0.92rem] py-4" style={{ color: 'var(--text-muted)' }}>
                No discussion captured — the full thread is on{' '}
                <a href={`https://t.me/NUSConfessIT/${postId}`} target="_blank" rel="noopener noreferrer"
                   className="font-semibold" style={{ color: 'var(--blue)' }}>Telegram</a>.
              </p>
            </div>
          )}
        </main>
      </>
    );
  }

  // Fall back to local SQLite
  const post = getPost(postId);
  if (!post) notFound();

  const replies = getReplies(postId);
  const totalInGroup = getTotalInGroup(postId);

  const label = post.confession_id ? `#${post.confession_id}` : `ID ${post.id}`;
  const tgUrl = `https://t.me/NUSConfessIT/${postId}`;
  const html = tgMdToHtml((post.content ?? post.text) ?? '');

  return (
    <>
      <Nav />
      <header
        className="text-white px-6 py-8"
        style={{ background: 'linear-gradient(135deg, #003D7C 0%, #00509E 100%)' }}
      >
        <div className="flex gap-5 mb-3.5 items-center flex-wrap">
          <Link href="/" className="text-white/65 no-underline text-[0.84rem] font-medium hover:text-white transition-colors">
            ← All Posts
          </Link>
          <a href={tgUrl} target="_blank" rel="noopener noreferrer"
             className="text-white/65 no-underline text-[0.84rem] font-medium hover:text-white transition-colors">
            View on Telegram ↗
          </a>
        </div>
        <h1 className="text-2xl font-bold">{post.title ?? `Confession ${label}`}</h1>
        <p className="text-white/75 mt-1.5 text-sm">
          {(post.date ?? '').slice(0, 10)} &middot; {label}
          {post.category && post.category !== 'Others' && ` · ${post.category}`}
        </p>
      </header>

      <main className="max-w-5xl mx-auto px-4 pb-16 pt-6">
        <div className="flex gap-5 flex-wrap items-center mb-5 text-[0.88rem]" style={{ color: 'var(--text-3)' }}>
          <span>❤️ <strong style={{ color: 'var(--text-1)' }}>{post.reactions_count}</strong></span>
          <span>💬 <strong style={{ color: 'var(--text-1)' }}>{post.reply_count}</strong></span>
          <span>↗ <strong style={{ color: 'var(--text-1)' }}>{post.forwards}</strong></span>
          <span>👁 <strong style={{ color: 'var(--text-1)' }}>{(post.views ?? 0).toLocaleString()}</strong></span>
        </div>

        <div className="reading-zone rounded-xl p-6 shadow-sm mb-7 text-[1rem] leading-[1.85]"
             style={{ background: 'var(--surface)', color: 'var(--text-1)' }}
             dangerouslySetInnerHTML={{ __html: html }} />

        {replies.length > 0 || totalInGroup > 0 ? (
          <section>
            <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
              <h2 className="text-[0.85rem] font-bold uppercase tracking-[0.8px] pb-2 border-b-2 inline-block m-0"
                  style={{ color: 'var(--blue)', borderColor: 'var(--orange)' }}>
                💬 Discussion
                {totalInGroup > 0 ? ` (${totalInGroup} in group)` : post.reply_count > 0 ? ` (${post.reply_count} comments)` : ''}
              </h2>
              <a href={tgUrl} target="_blank" rel="noopener noreferrer"
                 className="no-underline font-semibold px-3.5 py-1.5 rounded-full text-[0.82rem] whitespace-nowrap transition-all hover:opacity-80 hover:-translate-y-px inline-block"
                 style={{ background: 'var(--blue-light)', color: 'var(--blue)' }}>
                See all on Telegram ↗
              </a>
            </div>
            {replies.map((r, i) => (<ReplyCard key={r.id} reply={r} index={i} />))}
          </section>
        ) : (
          <div className="rounded-xl p-5 shadow-sm text-center" style={{ background: 'var(--surface)' }}>
            <p className="text-[0.92rem] py-4" style={{ color: 'var(--text-muted)' }}>
              No discussion captured — the full thread is on{' '}
              <a href={tgUrl} target="_blank" rel="noopener noreferrer" className="font-semibold" style={{ color: 'var(--blue)' }}>Telegram</a>.
            </p>
          </div>
        )}
      </main>
    </>
  );
}
