import Link from 'next/link';
import type { Post } from '@/lib/types';

interface ConfessionCardProps {
  post: Post;
  rank: number;
  q?: string;
}

function highlight(text: string, q: string): React.ReactNode {
  if (!q) return text;
  const idx = text.toLowerCase().indexOf(q.toLowerCase());
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <mark>{text.slice(idx, idx + q.length)}</mark>
      {text.slice(idx + q.length)}
    </>
  );
}

const RANK_COLORS: Record<number, string> = {
  1: '#FFD700',
  2: '#C0C0C0',
  3: '#CD7F32',
};

export function ConfessionCard({ post, rank, q = '' }: ConfessionCardProps) {
  const rankBg = RANK_COLORS[rank] ?? 'var(--blue)';
  const rankTextColor = rank <= 2 ? '#333' : '#fff';

  return (
    <Link href={`/post/${post.id}`} className="no-underline text-inherit block">
      <div
        className="border rounded-lg p-4 mb-2.5 flex gap-3.5 items-start
                   transition-shadow hover:shadow-md cursor-pointer"
        style={{
          borderColor: 'var(--border)',
          background: 'var(--surface)',
          animation: `card-in 0.32s cubic-bezier(0.22,1,0.36,1) both`,
          animationDelay: `${Math.min(rank - 1, 5) * 55}ms`,
        }}
      >
        {/* Rank badge */}
        <div
          className="shrink-0 w-9 h-9 rounded-full flex items-center justify-center font-black text-[0.9rem]"
          style={{ background: rankBg, color: rankTextColor }}
        >
          {rank}
        </div>

        {/* Body */}
        <div className="flex-1 min-w-0">
          {post.title && (
            <div
              className="font-bold text-[1rem] mb-1.5 leading-snug"
              style={{ color: 'var(--blue)' }}
            >
              {highlight(post.title, q)}
            </div>
          )}
          <div className="text-[0.93rem] leading-relaxed" style={{ color: 'var(--text-2)' }}>
            {highlight(post.excerpt, q)}
          </div>
          <div
            className="mt-2.5 flex gap-2 flex-wrap text-[0.74rem] items-center"
            style={{ color: 'var(--text-muted)' }}
          >
            {post.category && post.category !== 'Others' && (
              <span
                className="text-[0.72rem] font-semibold px-2 py-0.5 rounded-xl uppercase tracking-wide"
                style={{ background: 'var(--blue-light)', color: 'var(--blue)' }}
              >
                {post.category}
              </span>
            )}
            <span aria-label={`${post.reactions_count} reactions`}>
              ❤️ {post.reactions_count}
            </span>
            <span aria-label={`${post.reply_count} replies`}>
              💬 {post.reply_count}
            </span>
            <span aria-label={`${post.forwards} forwards`}>↗ {post.forwards}</span>
            <span aria-label={`${(post.views ?? 0).toLocaleString()} views`}>
              👁 {(post.views ?? 0).toLocaleString()}
            </span>
            <span>{(post.date ?? '').slice(0, 10)}</span>
            {post.confession_id && (
              <span style={{ color: 'var(--border)' }}>#{post.confession_id}</span>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
}
