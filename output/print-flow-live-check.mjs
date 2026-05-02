import { chromium } from 'file:///C:/final/frontend/node_modules/playwright/index.mjs';

const baseURL = 'http://127.0.0.1:5173';

const users = {
  registrar: {
    token: 'REDACTED_JWT',
    profile: {
      id: 20,
      username: 'registrar@example.com',
      full_name: 'Registrar User',
      email: 'registrar@example.com',
      role: 'Receptionist',
      is_active: true,
      is_superuser: false,
    },
  },
  cashier: {
    token: 'REDACTED_JWT',
    profile: {
      id: 23,
      username: 'cashier@example.com',
      full_name: 'Cashier User',
      email: 'cashier@example.com',
      role: 'Cashier',
      is_active: true,
      is_superuser: false,
    },
  },
};

async function newAuthedPage(browser, user) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.addInitScript(({ token, profile }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('auth_profile', JSON.stringify(profile));
    localStorage.setItem('user', JSON.stringify(profile));

    window.print = () => {
      window.__printCalled = true;
    };
    window.close = () => {
      window.__closeCalled = true;
    };
  }, { token: user.token, profile: user.profile });

  const page = await context.newPage();
  const requests = [];
  const consoleIssues = [];

  context.on('request', (request) => {
    const url = request.url();
    if (url.includes('/api/v1/print')) {
      requests.push({ method: request.method(), url });
    }
  });

  page.on('console', (msg) => {
    if (['error', 'warning'].includes(msg.type())) {
      consoleIssues.push({ type: msg.type(), text: msg.text() });
    }
  });

  return { context, page, requests, consoleIssues };
}

async function runTicketCheck(browser) {
  const { context, page, requests, consoleIssues } = await newAuthedPage(browser, users.registrar);
  await page.goto(`${baseURL}/registrar`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);

  const printButtons = page.locator('button[title="Печать"]');
  const buttonCount = await printButtons.count();
  if (buttonCount === 0) {
    await context.close();
    throw new Error('Ticket print button was not found on registrar panel');
  }

  await printButtons.first().click();
  await page.waitForTimeout(600);

  const dialogText = await page.locator('body').innerText();
  if (!dialogText.includes('Печать через браузер')) {
    await context.close();
    throw new Error('Ticket print dialog did not switch to browser-print mode');
  }

  const popupPromise = context.waitForEvent('page', { timeout: 8000 });
  await page.locator('button').filter({ hasText: /^Печать$/ }).last().click();
  const popup = await popupPromise;
  await popup.waitForLoadState('domcontentloaded');
  await popup.waitForTimeout(300);
  const popupText = await popup.locator('body').innerText();
  const printCalled = await popup.evaluate(() => Boolean(window.__printCalled));

  await context.close();

  return {
    buttonCount,
    popupText: popupText.slice(0, 500),
    printCalled,
    serverPrintRequests: requests,
    consoleIssues: consoleIssues.filter((item) => !item.text.includes('[setup] failed')),
  };
}

async function runReceiptCheck(browser) {
  const { context, page, requests, consoleIssues } = await newAuthedPage(browser, users.cashier);
  await page.goto(`${baseURL}/cashier`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  await page.getByText('История платежей').click();
  await page.waitForTimeout(1500);

  const receiptButtons = page.locator('button[title="Печать чека"]');
  const buttonCount = await receiptButtons.count();
  if (buttonCount === 0) {
    await context.close();
    throw new Error('Receipt print button was not found on cashier payment history');
  }

  const popupPromise = context.waitForEvent('page', { timeout: 8000 });
  await receiptButtons.first().click();
  const popup = await popupPromise;
  await popup.waitForLoadState('domcontentloaded');
  await popup.waitForTimeout(300);
  const popupText = await popup.locator('body').innerText();
  const printCalled = await popup.evaluate(() => Boolean(window.__printCalled));

  await context.close();

  return {
    buttonCount,
    popupText: popupText.slice(0, 500),
    printCalled,
    serverPrintRequests: requests,
    consoleIssues: consoleIssues.filter((item) => !item.text.includes('[setup] failed')),
  };
}

const browser = await chromium.launch({ headless: true });
try {
  const ticket = await runTicketCheck(browser);
  const receipt = await runReceiptCheck(browser);

  const result = {
    ticket,
    receipt,
    passed: (
      ticket.printCalled &&
      receipt.printCalled &&
      ticket.serverPrintRequests.length === 0 &&
      receipt.serverPrintRequests.length === 0 &&
      ticket.popupText.includes('ТАЛОН НА ПРИЁМ') &&
      receipt.popupText.includes('ЧЕК ОБ ОПЛАТЕ')
    ),
  };

  console.log(JSON.stringify(result, null, 2));
  if (!result.passed) {
    process.exitCode = 1;
  }
} finally {
  await browser.close();
}
