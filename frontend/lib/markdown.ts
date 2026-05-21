export function tgMdToHtml(raw: string): string {
  // Escape HTML first, then apply Telegram markdown transforms.
  let s = (raw ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Inline markup
  s = s.replace(
    /\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
  );
  s = s.replace(/\*\*(.+?)\*\*/gs, '<strong>$1</strong>');
  s = s.replace(/__(.+?)__/gs, '<em>$1</em>');
  s = s.replace(/~~(.+?)~~/gs, '<del>$1</del>');
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Block-level pass
  type Block = { type: 'p' | 'ul' | 'hr'; content: string[] };
  const blocks: Block[] = [];
  let para: string[] = [];
  let list: string[] = [];

  const flushPara = () => {
    if (para.length) { blocks.push({ type: 'p', content: [...para] }); para = []; }
  };
  const flushList = () => {
    if (list.length) { blocks.push({ type: 'ul', content: [...list] }); list = []; }
  };

  for (const line of s.split('\n')) {
    const stripped = line.trim();
    if (stripped === '---') {
      flushPara(); flushList();
      blocks.push({ type: 'hr', content: [] });
    } else if (/^-\s/.test(stripped)) {
      flushPara();
      list.push(stripped.slice(2).trim());
    } else if (!stripped) {
      flushPara(); flushList();
    } else {
      flushList();
      para.push(line);
    }
  }
  flushPara(); flushList();

  return blocks
    .map(b => {
      if (b.type === 'hr') return '<hr>';
      if (b.type === 'ul') return `<ul>${b.content.map(x => `<li>${x}</li>`).join('')}</ul>`;
      const inner = b.content.join('<br>');
      return inner.trim() ? `<p>${inner}</p>` : '';
    })
    .filter(Boolean)
    .join('\n');
}
