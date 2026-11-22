import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  use: {
    baseURL: 'http://localhost:4173',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  globalSetup: './e2e/globalSetup.ts',
  webServer: [
    {
      command: '..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000',
      cwd: './Backend/server',
      port: 8000,
      env: {
        DATABASE_URL: 'sqlite:///D:/Food_Project/Backend/server/e2e_food_guide.db',
        MOCK_AI: 'true',
        CORS_ORIGINS: 'http://localhost:4173,http://localhost:5173',
      },
    },
    {
      command: 'npm run preview -- --host 127.0.0.1 --port 4173',
      cwd: './client',
      port: 4173,
    },
  ],
});
