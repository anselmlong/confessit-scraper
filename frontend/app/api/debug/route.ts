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

  let fileSize = -1;
  try { fileSize = fs.statSync(dbPath).size; } catch { /* ignore */ }

  try {
    const Database = (await import('better-sqlite3')).default;
    const uri = `file:${dbPath.replace(/\\/g, '/')}?mode=ro&immutable=1`;
    const db = new Database(uri, { readonly: true });
    const row = db.prepare('SELECT COUNT(*) as cnt FROM messages WHERE is_reply=0').get() as { cnt: number };
    db.close();
    return NextResponse.json({ ...checks, fileSize, dbQueryOk: true, count: row.cnt });
  } catch (err) {
    return NextResponse.json({ ...checks, fileSize, dbQueryOk: false, error: String(err) });
  }
}
