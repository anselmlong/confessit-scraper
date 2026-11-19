import Link from 'next/link';
import type { Post } from '@/lib/types';
import { formatConfessionDate } from '@/lib/date';
import { HeartIcon, ReplyIcon } from './Icons';

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
    <Link href={`/post/${post.id}`} className="confession-link no-underline text-inherit block mb-2.5 rounded-xl">
      <div
        className="confession-card border rounded-xl p-4 md:p-5 flex gap-3 md:gap-4 items-start"
        style={{
          borderColor: 'var(--border)',
          background: 'var(--surface)',
          animation: `card-in 0.32s cubic-bezier(0.22,1,0.36,1) both`,
          animationDelay: `${Math.min(rank - 1, 5) * 55}ms`,
        }}
      >
        <div
          aria-hidden="true"
          className="card-rank shrink-0 w-6 md:w-7 pt-0.5 text-right text-[0.78rem] tabular-nums transition-colors"
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {rank}
        </div>

        {/* Body */}
        <div className="flex-1 min-w-0">
          {post.title && (
            <div className="card-title font-semibold text-[1rem] tracking-[-0.01em] mb-1.5 leading-snug text-balance">
              {highlight(post.title, q)}
            </div>
          )}
          <div className="card-excerpt text-[0.93rem] leading-relaxed line-clamp-5 text-pretty" style={{ color: 'var(--text-2)' }}>
            {highlight(post.excerpt, q)}
          </div>
          <div
            className="card-meta mt-3 flex gap-x-3.5 gap-y-1 flex-wrap tabular-nums text-[0.72rem] md:text-[0.74rem] items-center"
            style={{ color: 'var(--text-muted)' }}
          >
            {post.category && post.category !== 'Others' && (
              <span
                className="text-[0.7rem] md:text-[0.72rem] font-medium px-2 py-0.5 rounded-md border"
                style={{ borderColor: 'var(--border)', color: 'var(--text-2)', background: 'var(--surface-alt)' }}
              >
                {post.category}
              </span>
            )}
            <span className="inline-flex items-center gap-1"><HeartIcon /> {post.reactions_count}<span className="sr-only"> reactions</span></span>
            {post.reply_count > 0 && (
              <span className="inline-flex items-center gap-1"><ReplyIcon /> {post.reply_count}<span className="sr-only"> replies</span></span>
            )}
            <time dateTime={post.date ?? undefined}>{formatConfessionDate(post.date ?? '')}</time>
          </div>
        </div>
      </div>
    </Link>
  );
}
