import type { Post, Stats, MonthlyCount } from '@/lib/types';

const API = process.env.NEXT_PUBLIC_VPS_API || '';

async function fetchJSON(url: string) {
  if (!API) return null;
  try {
    const r = await fetch(url, { next: { revalidate: 300 } });
    if (!r.ok) return null;
    return r.json();
  } catch { return null; }
}

/* ── Posts ── */

export async function getPosts(opts: {
  sort: string; range: string; limit: number; q?: string; order?: string; start_date?: string; end_date?: string;
}): Promise<Post[]> {
  const p = new URLSearchParams({ sort: opts.sort, range: opts.range, n: String(opts.limit) });
  if (opts.q) p.set('q', opts.q);
  if (opts.order) p.set('order', opts.order);
  if (opts.start_date) p.set('start_date', opts.start_date);
  if (opts.end_date) p.set('end_date', opts.end_date);
  const data = await fetchJSON(`${API}/api/posts?${p}`);
  if (!data) return [];
  return data.map((d: any) => ({
    id: d.id, message_id: null, date: d.date, text: null, content: null,
    title: d.title || null, category: d.category || null, confession_id: null,
    reactions_count: d.reactions, reply_count: d.replies, forwards: d.forwards || 0,
    views: 0, is_reply: 0, reply_to_msg_id: null, word_count: null,
    score: d.score, excerpt: d.excerpt,
  }));
}

/* ── Stats ── */

export async function getStats(): Promise<Stats | null> {
  const d = await fetchJSON(`${API}/api/stats`);
  if (!d) return null;
  return {
    total: d.total_posts, first_date: d.first_date, last_date: d.last_date,
    total_views: d.total_views, avg_reactions: d.avg_reactions, avg_words: d.avg_words,
    max_reactions: d.max_reactions, total_replies: d.total_replies, days_active: d.days_active,
  };
}

/* ── Monthly ── */

export async function getMonthlyCounts(): Promise<MonthlyCount[]> {
  const data = await fetchJSON(`${API}/api/monthly`);
  if (!data) return [];
  return data.map((m: any) => ({ month: m.month, cnt: m.count }));
}

/* ── Single Post ── */

export async function getPost(id: number): Promise<{ post: Post; replies: any[]; total: number } | null> {
  const d = await fetchJSON(`${API}/api/post/${id}`);
  if (!d?.post) return null;
  return {
    post: {
      id: d.post.id, message_id: null, date: d.post.date, text: null,
      content: d.post.body || null, title: d.post.title || null,
      category: d.post.category || null, confession_id: null,
      reactions_count: d.post.reactions, reply_count: d.post.replies,
      forwards: d.post.forwards || 0, views: 0, is_reply: 0,
      reply_to_msg_id: null, word_count: null, score: d.post.score || 0,
      excerpt: (d.post.body || '').slice(0, 150),
    },
    replies: d.replies || [],
    total: d.total_replies_in_group || 0,
  };
}

/* ── Insights ── */

export async function getInsights() {
  return fetchJSON(`${API}/api/insights`);
}

export async function getLandscape() {
  return fetchJSON(`${API}/api/landscape`);
}