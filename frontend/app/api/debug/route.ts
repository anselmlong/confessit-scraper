import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export const runtime = 'nodejs';

export async function GET() {
  const cwd = process.cwd();
  const dbPath = path.join(cwd, 'messages.db');

  const checks = {
    cwd,
    dbPath,
    dbExists: fs.existsSync(dbPath),
    cwdContents: fs.existsSync(cwd) ? fs.readdirSync(cwd).slice(0, 20) : [],
  };

  try {
    // Try loading better-sqlite3
    const Database = (await import('better-sqlite3')).default;
    const db = new Database(dbPath, { readonly: true });
    const row = db.prepare('SELECT COUNT(*) as cnt FROM messages WHERE is_reply=0').get() as { cnt: number };
    db.close();
    return NextResponse.json({ ...checks, dbQueryOk: true, count: row.cnt });
  } catch (err) {
    return NextResponse.json({ ...checks, dbQueryOk: false, error: String(err) });
  }
}
