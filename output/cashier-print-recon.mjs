import { chromium } from 'file:///C:/final/frontend/node_modules/playwright/index.mjs';

const baseURL = 'http://127.0.0.1:5173';
const cashierToken = 'REDACTED_JWT';
const cashierProfile = {
  id: 23,
  username: 'cashier@example.com',
  full_name: 'Cashier User',
  email: 'cashier@example.com',
  role: 'Cashier',
  is_active: true,
  is_superuser: false,
};

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
await context.addInitScript(({ token, profile }) => {
  localStorage.setItem('auth_token', token);
  localStorage.setItem('auth_profile', JSON.stringify(profile));
  localStorage.setItem('user', JSON.stringify(profile));
}, { token: cashierToken, profile: cashierProfile });
const page = await context.newPage();
page.on('console', (msg) => console.log('[console]', msg.type(), msg.text()));

await page.goto(`${baseURL}/cashier`, { waitUntil: 'networkidle' });
await page.waitForTimeout(2000);
await page.getByText('История платежей').click();
await page.waitForTimeout(2000);
const storage = await page.evaluate(() => ({
  token: localStorage.getItem('auth_token'),
  profile: localStorage.getItem('auth_profile'),
  user: localStorage.getItem('user'),
}));

const buttons = await page.locator('button').evaluateAll((els) =>
  els.map((el) => ({
    text: (el.innerText || el.textContent || '').trim().replace(/\s+/g, ' '),
    disabled: el.disabled,
    aria: el.getAttribute('aria-label'),
    title: el.getAttribute('title'),
  })).filter((item) => item.text || item.aria || item.title)
);

console.log(JSON.stringify({
  url: page.url(),
  storage,
  buttons,
  textSample: (await page.locator('body').innerText()).slice(0, 2500),
}, null, 2));

await browser.close();
