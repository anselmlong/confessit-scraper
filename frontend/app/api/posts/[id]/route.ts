import { NextRequest, NextResponse } from 'next/server';
import { getPost, getReplies, getTotalInGroup } from '@/lib/db';

export const runtime = 'nodejs';

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const postId = parseInt(id, 10);

  try {
    const post = getPost(postId);
    if (!post) return NextResponse.json({ error: 'Not found' }, { status: 404 });
    const replies = getReplies(postId);
    const totalInGroup = getTotalInGroup(postId);
    return NextResponse.json({ post, replies, totalInGroup });
  } catch (err) {
    console.error(err);
    return NextResponse.json({ error: 'Failed to fetch post' }, { status: 500 });
  }
}
