import { chromium } from 'file:///C:/final/frontend/node_modules/playwright/index.mjs';

const baseURL = 'http://127.0.0.1:5173';
const registrarToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMCIsInVzZXJfaWQiOjIwLCJ1c2VybmFtZSI6InJlZ2lzdHJhckBleGFtcGxlLmNvbSIsImV4cCI6MTc3NTc2OTczNH0.OpTBdvzuWxfIDXm-VcO-8i4w0T3nk6FR56Yc95kOng4';
const registrarProfile = {
  id: 20,
  username: 'registrar@example.com',
  full_name: 'Registrar User',
  email: 'registrar@example.com',
  role: 'Receptionist',
  is_active: true,
  is_superuser: false,
};

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();

const consoleMessages = [];
page.on('console', (msg) => {
  const type = msg.type();
  if (['error', 'warning'].includes(type)) {
    consoleMessages.push({ type, text: msg.text() });
  }
});

await page.goto(baseURL, { waitUntil: 'domcontentloaded' });
await page.evaluate(({ token, profile }) => {
  localStorage.setItem('auth_token', token);
  localStorage.setItem('auth_profile', JSON.stringify(profile));
  localStorage.setItem('user', JSON.stringify(profile));
}, { token: registrarToken, profile: registrarProfile });
await page.goto(`${baseURL}/registrar`, { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);

const buttons = await page.locator('button').evaluateAll((els) =>
  els.map((el) => ({
    text: (el.innerText || el.textContent || '').trim().replace(/\s+/g, ' '),
    disabled: el.disabled,
    aria: el.getAttribute('aria-label'),
    title: el.getAttribute('title'),
  })).filter((item) => item.text || item.aria || item.title)
);

const inputs = await page.locator('input, textarea, select').evaluateAll((els) =>
  els.map((el) => ({
    tag: el.tagName.toLowerCase(),
    type: el.getAttribute('type'),
    name: el.getAttribute('name'),
    placeholder: el.getAttribute('placeholder'),
    aria: el.getAttribute('aria-label'),
    value: el.value,
  }))
);

console.log(JSON.stringify({
  url: page.url(),
  title: await page.title(),
  buttons,
  inputs,
  consoleMessages,
}, null, 2));

await browser.close();
