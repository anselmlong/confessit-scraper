import { NextResponse } from 'next/server';
import { getStats, getMonthlyCounts } from '@/lib/db';

export const runtime = 'nodejs';

export async function GET() {
  try {
    const stats = getStats();
    const monthly = getMonthlyCounts();
    return NextResponse.json({ stats, monthly });
  } catch (err) {
    console.error(err);
    return NextResponse.json({ error: 'Failed to fetch stats' }, { status: 500 });
  }
}
