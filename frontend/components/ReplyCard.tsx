import type { Reply } from '@/lib/types';
import { tgMdToHtml } from '@/lib/markdown';

export function ReplyCard({ reply, index }: { reply: Reply; index: number }) {
  const html = tgMdToHtml((reply.content ?? reply.text) ?? '');
  return (
    <div
      className="rounded-lg p-3.5 mb-2.5 border"
      style={{
        background: 'var(--surface)',
        borderColor: 'var(--border-light)',
        animation: `card-in 0.32s cubic-bezier(0.22,1,0.36,1) ${Math.min(index, 7) * 50}ms both`,
      }}
    >
      {reply.author && (
        <div className="text-[0.76rem] font-semibold mb-1.5" style={{ color: 'var(--text-3)' }}>
          {reply.author}
        </div>
      )}
      <div
        className="reading-zone text-[0.88rem] leading-relaxed"
        style={{ color: 'var(--text-2)' }}
        dangerouslySetInnerHTML={{ __html: html }}
      />
      <div className="mt-2 text-[0.74rem] flex gap-3" style={{ color: 'var(--text-muted)' }}>
        <span>{(reply.date ?? '').slice(0, 10)}</span>
        {(reply.reactions_up ?? 0) > 0 && <span>👍 {reply.reactions_up}</span>}
        {(reply.reactions_down ?? 0) > 0 && <span>👎 {reply.reactions_down}</span>}
        {(reply.reactions_count ?? 0) > 0 && <span>❤️ {reply.reactions_count}</span>}
      </div>
    </div>
  );
}
