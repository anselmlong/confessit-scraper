import Link from 'next/link';
import type { Post } from '@/lib/types';
import { formatConfessionDate } from '@/lib/date';

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

export function ConfessionCard({ post, rank, q = '' }: ConfessionCardProps) {
  return (
    <Link href={`/post/${post.id}`} className="no-underline text-inherit block mb-2.5 rounded-lg">
      <div
        className="confession-card border rounded-lg p-3.5 md:p-4 flex gap-3 md:gap-3.5 items-start"
        style={{
          borderColor: 'var(--border)',
          background: 'var(--surface)',
          animation: `card-in 0.32s cubic-bezier(0.22,1,0.36,1) both`,
          animationDelay: `${Math.min(rank - 1, 5) * 55}ms`,
        }}
      >
        {/* Rank badge */}
        <div
          aria-hidden="true"
          className="card-rank shrink-0 w-7 h-7 md:w-9 md:h-9 rounded-full flex items-center justify-center font-black text-[0.78rem] md:text-[0.9rem] tabular-nums"
          style={{ background: 'var(--surface-mid)', color: 'var(--text-3)' }}
        >
          {rank}
        </div>

        {/* Body */}
        <div className="flex-1 min-w-0">
          {post.title && (
            <div
              className="font-bold text-[1rem] mb-1.5 leading-snug text-balance"
              style={{ color: 'var(--blue)' }}
            >
              {highlight(post.title, q)}
            </div>
          )}
          <div className="card-excerpt text-[0.93rem] leading-relaxed line-clamp-5 text-pretty" style={{ color: 'var(--text-2)' }}>
            {highlight(post.excerpt, q)}
          </div>
          <div
            className="card-meta mt-2.5 flex gap-x-2.5 gap-y-1 flex-wrap tabular-nums text-[0.72rem] md:text-[0.74rem] items-center"
            style={{ color: 'var(--text-muted)' }}
          >
            {post.category && post.category !== 'Others' && (
              <span
                className="text-[0.7rem] md:text-[0.72rem] font-semibold px-1.5 md:px-2 py-0.5 rounded-xl uppercase tracking-wide"
                style={{ background: 'var(--blue-light)', color: 'var(--blue)' }}
              >
                {post.category}
              </span>
            )}
            <span><span aria-hidden="true">❤️</span> {post.reactions_count}<span className="sr-only"> reactions</span></span>
            {post.reply_count > 0 && (
              <span><span aria-hidden="true">💬</span> {post.reply_count}<span className="sr-only"> replies</span></span>
            )}
            <time dateTime={post.date ?? undefined}>{formatConfessionDate(post.date ?? '')}</time>
          </div>
        </div>
      </div>
    </Link>
  );
}
