import { test, expect } from '@playwright/test';

test('guards redirect guests and show not found', async ({ page }) => {
  await page.goto('/itinerary');
  await expect(page).toHaveURL(/\/login/);
  await page.goto('/admin');
  await expect(page).toHaveURL(/\/login/);
  await page.goto('/unknown-page');
  await expect(page.getByRole('heading', { name: 'Không tìm thấy trang' })).toBeVisible();
});

test('USER admin guard shows forbidden', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill('demo1@example.com');
  await page.getByLabel('Mật khẩu').fill('demo-password-123');
  await page.getByRole('button', { name: 'Đăng nhập' }).click();
  await expect(page).not.toHaveURL(/\/login/);
  await page.goto('/admin');
  await expect(page.getByRole('heading', { name: 'Bạn chưa có quyền truy cập' })).toBeVisible();
});

test('mock search returns detected foods and no extra requests on chip selection', async ({ page }) => {
  await page.goto('/search');
  const png = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
    'base64'
  );
  await page.getByLabel('Chọn hoặc chụp ảnh món ăn').setInputFiles({
    name: 'food.png',
    mimeType: 'image/png',
    buffer: png,
  });
  await page.getByRole('button', { name: /Tìm món ăn/ }).click();
  await expect(page.getByText('Đây có thể là món gì?')).toBeVisible();
  await expect(page.locator('.detected-chip')).toHaveCount(2);

  const extraRequests: string[] = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (url.origin === 'http://localhost:8000' &&
      /\/(foods|restaurants)(\?|\/|$)/.test(url.pathname)) extraRequests.push(request.url());
  });
  await page.locator('.detected-chip').nth(1).click();
  await expect(page.getByText(/Quán bán/)).toBeVisible();
  expect(extraRequests).toHaveLength(0);
});

test('itinerary login and cache generate', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill('demo1@example.com');
  await page.getByLabel('Mật khẩu').fill('demo-password-123');
  await page.getByRole('button', { name: 'Đăng nhập' }).click();
  await expect(page).not.toHaveURL(/\/login/);
  await page.goto('/itinerary');
  await page.locator('.itinerary-intro').getByRole('button', { name: /Tạo lộ trình hôm nay/ }).click();
  await expect(page.locator('.stop-card')).toHaveCount(4);
  await expect(page.locator('.itinerary-map .food-map-marker')).toHaveCount(4);
  await expect(page.getByText('Gợi ý theo đánh giá').first()).toBeVisible();
});
