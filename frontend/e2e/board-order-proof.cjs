const assert = require('node:assert/strict');
const { chromium, expect } = require('@playwright/test');
const base = 'http://127.0.0.1:18586';
const title = (board) => board === 'synthetic-a' ? 11 : 27;
const rows = (board, status) => [{id:title(board), queue_id:title(board), number:title(board), status}];
const snap = (queue_entries, current_call=null) => ({type:'initial_state',data:{queue_entries,current_call,announcements:[]}});
const update = (board, status) => ({type:'queue_update',event_type:'queue.updated',data:{queue_id:title(board),queue_entries:rows(board,status)}});
const call = {queue_number:11, queue_id:11, queue_entry_id:11, event_id:'synthetic-live-1', issued_at:new Date().toISOString(), expires_at:new Date(Date.now()+90000).toISOString(), cabinet:'101'};
const invitation = '.displayboard-call-number';
const row = '.displayboard-queue-number';
async function createPage(browser, board, initial) {
  const ctx = await browser.newContext({serviceWorkers:'block'});
  const page = await ctx.newPage();
  const requests=[], sockets=[], failures=[];
  page.on('pageerror', e=>failures.push(e.message));
  await page.route('**/*', async r => {
    if (new URL(r.request().url()).origin === base) return r.continue();
    await r.abort();
  });
  await page.route('**/api/v1/**', async r=>{
    const path = new URL(r.request().url()).pathname;
    const data = path.endsWith('/setup/status') ? {initialized:true}
      : path.endsWith('/display/devices/token') ? {access_token:'synthetic-local-fixture', token_type:'bearer', expires_in:900, board_name:board}
      : path.endsWith('/board/state') ? {is_open:true, sound_enabled:false, display_count:5}
      : {success:true};
    await r.fulfill({status:path.endsWith('/auth/me')?401:200,json:data});
  });
  await page.routeWebSocket('**/api/v1/display/ws/board/*', ws=>{
    assert.equal(new URL(ws.url()).pathname.split('/').at(-1),board);
    sockets.push(ws);
    ws.onMessage(payload=>{if(JSON.parse(payload).type==='request_update') requests.push(ws);});
    ws.send(JSON.stringify(sockets.length===1?initial:snap(rows(board,'waiting'))));
  });
  await page.goto(base+'/display-board?board='+board);
  await expect.poll(()=>sockets.length).toBe(1);
  const push=(value)=>sockets.at(-1).send(JSON.stringify(value));
  return {page,requests,sockets,failures,push};
}
(async()=>{
  const browser = await chromium.launch({headless:true});
  try {
    const [a,b] = await Promise.all([
      createPage(browser,'synthetic-a',snap(rows('synthetic-a','called'),call)),
      createPage(browser,'synthetic-b',snap(rows('synthetic-b','waiting'))),
    ]);
    await expect(a.page.locator(invitation)).toContainText('11');
    await expect(b.page.locator(row)).toHaveText('27');
    a.push(update('synthetic-a','waiting')); a.push(update('synthetic-a','waiting'));
    if (process.env.PROOF_BASELINE === '1') {
      await expect(a.page.locator(invitation)).toHaveCount(0);
      await expect(a.page.locator(row)).toHaveText('11');
      a.push(snap([])); await expect(a.page.locator(row)).toHaveCount(0);
      a.push(update('synthetic-a','called'));
      await expect(a.page.locator(row)).toHaveText('11');
      assert.equal(a.requests.length,0);
      console.log('BASELINE REPRODUCED: stale waiting removed a confirmed invitation; stale called restored a terminal row');
      return;
    }
    await expect.poll(()=>a.requests.length).toBe(1);
    await expect(a.page.locator(invitation)).toContainText('11');
    a.push(snap(rows('synthetic-a','called'),call));
    await expect(a.page.locator(invitation)).toContainText('11');
    a.push(update('synthetic-a','waiting'));
    await expect.poll(()=>a.requests.length).toBe(2);
    a.push(snap([]));
    await expect(a.page.locator(invitation)).toHaveCount(0);
    a.push(update('synthetic-a','called'));
    await expect.poll(()=>a.requests.length).toBe(3);
    await expect(a.page.locator(row)).toHaveCount(0);
    a.push(snap([]));
    await expect(b.page.locator(row)).toHaveText('27');
    assert.equal(b.requests.length,0);
    a.sockets.at(-1).close({code:1012,reason:'synthetic-restart'});
    await expect.poll(()=>a.sockets.length,{timeout:7500}).toBe(2);
    await expect(a.page.locator(row)).toHaveText('11');
    await expect(a.page.locator(invitation)).toHaveCount(0);
    assert.equal(b.sockets.length,1);
    assert.deepEqual(a.failures,[]); assert.deepEqual(b.failures,[]);
    console.log('PASS: real Chromium; two isolated browser contexts; DOM call stable after late update, single snapshot request, terminal state confirmed, old called row not restored, WS reconnect restores waiting without invitation');
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
