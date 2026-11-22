import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

export default function globalSetup() {
  const server = path.resolve('Backend/server');
  const python = path.resolve('Backend/.venv/Scripts/python.exe');
  const db = path.join(server, 'e2e_food_guide.db');
  if (fs.existsSync(db)) fs.rmSync(db);
  execFileSync(python, ['-m', 'alembic', 'upgrade', 'head'], {
    cwd: server,
    env: { ...process.env, DATABASE_URL: 'sqlite:///D:/Food_Project/Backend/server/e2e_food_guide.db', MOCK_AI: 'true' },
  });
  execFileSync(python, ['scripts/seed.py'], {
    cwd: server,
    env: { ...process.env, DATABASE_URL: 'sqlite:///D:/Food_Project/Backend/server/e2e_food_guide.db', MOCK_AI: 'true' },
  });
}
