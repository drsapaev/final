const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const dir = process.env.WORKLIST_PROOF_DIR;
const actors = JSON.parse(fs.readFileSync(path.join(dir, 'fixture.json'), 'utf8'));
const api = 'http://127.0.0.1:' + process.env.APIPORT;
const web = 'http://127.0.0.1:' + process.env.WEBPORT;
const endpoint = '/api/v1/doctor/dentistry/queue/today';

async function login(mode) {
  const response = await fetch(api + '/api/v1/authentication/login', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'synthetic-' + mode, password: process.env.WORKLIST_PROOF_PASSWORD }),
  });
  assert.equal(response.status, 200);
  return (await response.json()).access_token;
}
async function queue(token, day) {
  const response = await fetch(api + endpoint, { headers: { Authorization: 'Bearer ' + token } });
  assert.equal(response.status, 200);
  const data = await response.json();
  assert.equal(data.date, day);
  return data;
}

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  try {
    for (const [day, instant] of [
      ['2026-11-25', '2026-11-25T18:59:00+00:00'],
      ['2026-11-26', '2026-11-25T19:00:00+00:00'],
    ]) {
      fs.writeFileSync(path.join(dir, 'instant'), instant);
      for (const mode of ['manual', 'complete', 'finish']) {
        const actor = actors[mode];
        const row = actor.days[day];
        const token = await login(mode);
        assert.equal((await queue(token, day)).next_call_entry_id, row.winner);
        const page = await browser.newPage({ timezoneId: 'UTC', locale: 'ru-RU' });
        try {
          page.setDefaultTimeout(25000);
          await page.clock.setFixedTime(new Date(instant));
          await page.addInitScript(({ token, actor, row, mode }) => {
            sessionStorage.setItem('auth_token', token);
            sessionStorage.setItem('auth_profile', JSON.stringify({
              id: actor.user, doctor_id: actor.doctor, role: 'Doctor',
            }));
            sessionStorage.setItem('call_flow_proof', JSON.stringify({ ...row, doctor: actor.doctor, mode }));
          }, { token, actor, row, mode });
          const writes = [];
          page.on('request', r => {
            if (r.method() === 'POST' && /(?:\/call-next|\/call|\/complete)(?:$|\?)/.test(r.url())) {
              writes.push(new URL(r.url()).pathname);
            }
          });
          await page.goto(web + '/e2e/call-flow-proof/index.html');
          if (mode === 'manual') {
            const button = page.locator('button[title="Backend call-next command"]');
            await button.waitFor();
            const request = page.waitForResponse(r => r.request().method() === 'POST' && r.url().includes('/call-next'));
            await button.click();
            assert.equal((await request).status(), 200);
          } else {
            await page.getByRole('button', { name: 'Complete synthetic visit' }).click();
            const dialog = page.getByRole('dialog');
            const option = dialog.getByRole('checkbox');
            assert.equal(await option.isChecked(), false);
            if (mode === 'complete') await option.check();
            await dialog.getByRole('button', { name: 'dental.dental_panel_complete_confirm', exact: true }).click();
            await page.waitForFunction(() => document.querySelector('[aria-label="Completion outcome"]')?.textContent === 'true');
            if (mode === 'complete') {
              await page.getByText('misc.queue_called_display_unconfirmed', { exact: true }).waitFor();
            }
          }
          const final = new Map((await queue(token, day)).entries.map(row => [row.id, row.status]));
          assert.equal(final.get(row.other), 'waiting');
          assert.equal(final.get(row.winner), mode === 'finish' ? 'waiting' : 'called');
          assert.equal(final.get(row.current), mode === 'manual' ? 'in_progress' : 'served');
          assert.equal(writes.length, mode === 'complete' ? 2 : 1, JSON.stringify(writes));
          if (mode !== 'manual') assert.ok(writes[0].endsWith('/' + row.current + '/complete'));
          if (mode === 'complete') assert.ok(writes[1].endsWith('/' + row.winner + '/call'));
          console.log(day + ' ' + mode + ': expected persisted priority, completion state and command count');
        } finally {
          await page.close();
        }
      }
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
