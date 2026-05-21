import Database from 'better-sqlite3';
import { copyFileSync, existsSync } from 'fs';
import path from 'path';
import type { Post, Reply, Stats, MonthlyCount } from './types';

declare global {
  // eslint-disable-next-line no-var
  var _confessitDb: Database.Database | undefined;
}

function getDb(): Database.Database {
  if (!global._confessitDb) {
    const srcPath = process.env.DB_PATH ?? path.join(process.cwd(), 'messages.db');
    try {
      // Try opening in place first (works in local dev)
      global._confessitDb = new Database(srcPath, { readonly: true, fileMustExist: true });
    } catch {
      // Vercel Lambda: /var/task is read-only; SQLite needs a writable dir for lock
      // files even in readonly mode. Copy the DB to /tmp and open from there.
      const tmp = '/tmp/confessit-messages.db';
      if (!existsSync(tmp)) copyFileSync(srcPath, tmp);
      global._confessitDb = new Database(tmp, { readonly: true, fileMustExist: true });
    }
  }
  return global._confessitDb;
}

const SCORE = '(reactions_count * 3 + reply_count * 2 + forwards)';

const SORTS: Record<string, string> = {
  score: SCORE,
  reactions: 'reactions_count',
  replies: 'reply_count',
};

const RANGE_DAYS: Record<string, number | null> = {
  week: 7,
  month: 30,
  year: 365,
  all: null,
};

function buildExcerpt(text: string, maxChars = 300): string {
  const clean = (text ?? '').trim()
    .replace(/\*\*(.+?)\*\*/gs, '$1')
    .replace(/__(.+?)__/gs, '$1')
    .replace(/~~(.+?)~~/gs, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
  if (clean.length <= maxChars) return clean;
  return clean.slice(0, maxChars).replace(/\s+\S*$/, '') + '…';
}

export function getPosts({
  range = 'week',
  sort = 'reactions',
  q,
  limit = 25,
}: {
  range?: string;
  sort?: string;
  q?: string;
  limit?: number;
}): Post[] {
  const db = getDb();
  const days = RANGE_DAYS[range] ?? RANGE_DAYS.week;
  const orderExpr = SORTS[sort] ?? SORTS.reactions;

  let sql = `SELECT *, ${SCORE} AS score FROM messages WHERE is_reply=0`;
  const params: (string | number)[] = [];

  if (days !== null) {
    const since = new Date(Date.now() - days * 86_400_000).toISOString();
    sql += ' AND date >= ?';
    params.push(since);
  }

  if (q) {
    const like = `%${q}%`;
    sql += ' AND (text LIKE ? OR title LIKE ? OR content LIKE ?)';
    params.push(like, like, like);
  }

  sql += ` ORDER BY ${orderExpr} DESC LIMIT ?`;
  params.push(limit);

  const rows = db.prepare(sql).all(...params) as Omit<Post, 'excerpt'>[];
  return rows.map(r => ({
    ...r,
    excerpt: buildExcerpt((r.content ?? r.text) ?? ''),
  }));
}

export function getPostCount({ range = 'week', q }: { range?: string; q?: string }): number {
  const db = getDb();
  const days = RANGE_DAYS[range] ?? RANGE_DAYS.week;

  let sql = 'SELECT COUNT(*) AS cnt FROM messages WHERE is_reply=0';
  const params: (string | number)[] = [];

  if (days !== null) {
    const since = new Date(Date.now() - days * 86_400_000).toISOString();
    sql += ' AND date >= ?';
    params.push(since);
  }

  if (q) {
    const like = `%${q}%`;
    sql += ' AND (text LIKE ? OR title LIKE ? OR content LIKE ?)';
    params.push(like, like, like);
  }

  const row = db.prepare(sql).get(...params) as { cnt: number };
  return row.cnt;
}

export function getStats(): Stats {
  const db = getDb();

  const raw = db.prepare(`
    SELECT
      COUNT(*) AS total,
      MIN(date) AS first_date,
      MAX(date) AS last_date,
      SUM(views) AS total_views,
      ROUND(AVG(reactions_count), 1) AS avg_reactions,
      ROUND(AVG(word_count), 0) AS avg_words,
      MAX(reactions_count) AS max_reactions
    FROM messages WHERE is_reply=0
  `).get() as {
    total: number; first_date: string; last_date: string;
    total_views: number; avg_reactions: number; avg_words: number; max_reactions: number;
  };

  const { cnt: totalReplies } = db.prepare(
    'SELECT COUNT(*) AS cnt FROM replies'
  ).get() as { cnt: number };

  const firstDate = (raw.first_date ?? '').slice(0, 10);
  const lastDate = (raw.last_date ?? '').slice(0, 10);
  let daysActive = 0;
  try {
    daysActive = Math.floor(
      (new Date(lastDate).getTime() - new Date(firstDate).getTime()) / 86_400_000
    );
  } catch { /* ignore */ }

  return {
    ...raw,
    first_date: firstDate,
    last_date: lastDate,
    total_views: raw.total_views ?? 0,
    avg_reactions: raw.avg_reactions ?? 0,
    avg_words: raw.avg_words ?? 0,
    max_reactions: raw.max_reactions ?? 0,
    total_replies: totalReplies,
    days_active: daysActive,
  };
}

export function getMonthlyCounts(): MonthlyCount[] {
  const db = getDb();
  const rows = db.prepare(`
    SELECT strftime('%Y-%m', date) AS month, COUNT(*) AS cnt
    FROM messages WHERE is_reply=0 AND date IS NOT NULL
    GROUP BY month ORDER BY month DESC LIMIT 18
  `).all() as MonthlyCount[];
  return rows.reverse();
}

export function getPost(id: number): Post | null {
  const db = getDb();
  const row = db.prepare(
    `SELECT *, ${SCORE} AS score FROM messages WHERE id=? AND is_reply=0`
  ).get(id) as Omit<Post, 'excerpt'> | undefined;
  if (!row) return null;
  return { ...row, excerpt: buildExcerpt((row.content ?? row.text) ?? '') };
}

export function getReplies(postId: number): Reply[] {
  const db = getDb();
  const inline = db.prepare(
    'SELECT * FROM messages WHERE reply_to_msg_id=? ORDER BY date ASC'
  ).all(postId) as Reply[];
  const discussion = db.prepare(
    'SELECT * FROM replies WHERE post_id=? ORDER BY date ASC'
  ).all(postId) as Reply[];
  return [...inline, ...discussion];
}

export function getTotalInGroup(postId: number): number {
  const db = getDb();
  const row = db.prepare(
    'SELECT COUNT(*) AS cnt FROM replies WHERE post_id=?'
  ).get(postId) as { cnt: number };
  return row.cnt;
}
