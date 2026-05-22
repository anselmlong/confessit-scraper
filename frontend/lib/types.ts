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
