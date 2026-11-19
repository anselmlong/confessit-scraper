export interface Post {
  id: number;
  message_id: number | null;
  date: string;
  text: string | null;
  content: string | null;
  title: string | null;
  category: string | null;
  confession_id: number | null;
  reactions_count: number;
  reply_count: number;
  forwards: number;
  views: number;
  is_reply: number;
  reply_to_msg_id: number | null;
  word_count: number | null;
  score: number;
  excerpt: string;
}

export interface Reply {
  id: number;
  post_id?: number;
  reply_to_msg_id?: number;
  date: string;
  text: string | null;
  content?: string | null;
  author: string | null;
  reactions_count: number | null;
  reactions_up: number | null;
  reactions_down: number | null;
}

export interface Stats {
  total: number;
  first_date: string;
  last_date: string;
  total_views: number;
  avg_reactions: number;
  avg_words: number;
  max_reactions: number;
  total_replies: number;
  days_active: number;
}

export interface MonthlyCount {
  month: string;
  cnt: number;
}

export type SortKey = 'time' | 'reactions' | 'replies' | 'score';
export type RangeKey = 'week' | 'month' | 'year' | 'all' | 'custom';
export type OrderKey = 'asc' | 'desc';

export interface CopypastaCluster {
  key: string;
  name: string;
  count: number;
  avg_score: number;
  avg_reactions: number;
  sample_text: string;
  sample_id: number;
  trend_30d: number;
  is_trending: boolean;
}

export interface CopypastaData {
  clusters: CopypastaCluster[];
  exact_duplicates: {
    unique_texts: number;
    total_duplicate_posts: number;
    pct_of_all_posts: number;
  };
}

/* ── Trends ── */

export type TimelineSpan = '30d' | '90d' | '1y' | 'all';

export interface MomentPost {
  id: number;
  day: string;
  score: number;
  reactions: number;
  replies: number;
  excerpt: string;
}

export interface TimelineBucket {
  start: string;
  end: string;
  count: number;
  avg_score: number;
  /** Still collecting reactions: engagement will rise. */
  provisional: boolean;
  /** Bucket runs past today: volume is incomplete. */
  partial: boolean;
  top: MomentPost[];
}

export interface Moment {
  kind: 'spike' | 'viral';
  start: string;
  end: string;
  ratio: number | null;
  count: number | null;
  post: MomentPost | null;
}

export interface Timeline {
  span: TimelineSpan;
  bucket: 'day' | 'week';
  provisional_from: string;
  series: TimelineBucket[];
  moments: Moment[];
}

export interface SharePoint { month: string; count: number; share: number }

export interface TermTrend {
  term: string;
  total: number;
  peak: { month: string; share: number; count: number } | null;
  series: (SharePoint & { total: number })[];
}

export interface CategoryTrend {
  category: string;
  total: number;
  series: SharePoint[];
}
