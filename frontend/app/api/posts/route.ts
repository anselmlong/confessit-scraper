import { NextRequest, NextResponse } from 'next/server';
import { getPosts, getPostCount } from '@/lib/db';

export const runtime = 'nodejs';

export async function GET(request: NextRequest) {
  const sp = request.nextUrl.searchParams;
  const range = sp.get('range') ?? 'week';
  const sort = sp.get('sort') ?? 'reactions';
  const q = sp.get('q') ?? '';
  const limit = Math.min(parseInt(sp.get('limit') ?? '25', 10) || 25, 200);

  try {
    const posts = getPosts({ range, sort, q: q || undefined, limit });
    const total = getPostCount({ range, q: q || undefined });
    return NextResponse.json({ posts, total });
  } catch (err) {
    console.error(err);
    return NextResponse.json({ error: 'Failed to fetch posts' }, { status: 500 });
  }
}
