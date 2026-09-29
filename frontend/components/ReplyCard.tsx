import type { Reply } from '@/lib/types';
import { tgMdToHtml } from '@/lib/markdown';
import { formatShortDate } from '@/lib/date';

export function ReplyCard({ reply, index }: { reply: Reply; index: number }) {
  const html = tgMdToHtml((reply.content ?? reply.text) ?? '');
  return (
    <div
      className="rounded-lg p-3 md:p-3.5 mb-2 border"
      style={{
        background: 'var(--surface)',
        borderColor: 'var(--border-light)',
        animation: `card-in 0.32s cubic-bezier(0.22,1,0.36,1) ${Math.min(index, 7) * 50}ms both`,
      }}
    >
      {reply.author && (
        <div className="text-[0.74rem] md:text-[0.76rem] font-semibold mb-1 md:mb-1.5" style={{ color: 'var(--text-3)' }}>
          {reply.author}
        </div>
      )}
      <div
        className="reading-zone text-[0.85rem] md:text-[0.88rem] leading-relaxed"
        style={{ color: 'var(--text-2)' }}
        dangerouslySetInnerHTML={{ __html: html }}
      />
      <div className="mt-1.5 md:mt-2 text-[0.7rem] md:text-[0.74rem] flex gap-2 md:gap-3" style={{ color: 'var(--text-muted)' }}>
        <time dateTime={reply.date || undefined}>{formatShortDate(reply.date ?? '')}</time>
        {(reply.reactions_up ?? 0) > 0 && <span><span aria-hidden="true">👍</span> {reply.reactions_up}<span className="sr-only"> upvotes</span></span>}
        {(reply.reactions_down ?? 0) > 0 && <span><span aria-hidden="true">👎</span> {reply.reactions_down}<span className="sr-only"> downvotes</span></span>}
        {(reply.reactions_count ?? 0) > 0 && <span><span aria-hidden="true">❤️</span> {reply.reactions_count}<span className="sr-only"> reactions</span></span>}
      </div>
    </div>
  );
}
