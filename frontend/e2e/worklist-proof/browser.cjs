const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const proofDir = process.env.WORKLIST_PROOF_DIR;
const rows = JSON.parse(fs.readFileSync(path.join(proofDir, 'fixture.json'), 'utf8'));
const api = 'http://127.0.0.1:' + process.env.APIPORT;
const app = 'http://127.0.0.1:' + process.env.WEBPORT;
const endpoint = '/api/v1/doctor/dermatology/queue/today';
const before = '2026-11-25T18:59:00+00:00', after = '2026-11-25T19:00:00+00:00';
function clock(t) { fs.writeFileSync(path.join(proofDir, 'instant'), t); }
async function login(actor) {
  const res = await fetch(api + '/api/v1/authentication/login', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ username: 'synthetic-' + actor, password: process.env.WORKLIST_PROOF_PASSWORD }),
  });
  assert.equal(res.status, 200);
  const { access_token } = await res.json();
  assert.ok(access_token);
  return access_token;
}
async function projection(token, date, row, status='called') {
  const res = await fetch(api + endpoint, {headers:{Authorization:'Bearer '+token}});
  assert.equal(res.status,200);
  const result = await res.json();
  assert.equal(result.date,date);
  assert.equal(result.doctor.id,row.doctor);
  assert.deepEqual(result.entries.map(e=>[e.id,e.status,e.can_start_visit]),[[row.entry,status,status==='called']]);
}
(async () => {
  clock(before);
  const token=await login('owner');
  await projection(token,'2026-11-25',rows.OLD);
  const browser=await chromium.launch({executablePath:process.env.CHROME_BINARY,args:['--no-sandbox']});
  try {
    const page=await browser.newPage({timezoneId:'UTC',locale:'ru-RU'});
    page.setDefaultTimeout(30000);
    page.on('pageerror',e=>console.error('PAGEERROR',e.message));
    await page.addInitScript(({token,row})=>{
      sessionStorage.setItem('auth_token',token);
      sessionStorage.setItem('auth_profile',JSON.stringify({id:row.user,doctor_id:row.doctor,role:'derma'}));
    },{token,row:rows.OLD});
    await page.clock.setFixedTime(new Date(before));
    const posts=[];
    page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/start-visit'))posts.push(r.url().match(/queue\/(\d+)/)?.[1]);});
    await page.goto(app+'/e2e/worklist-proof/index.html');
    const date=page.locator('#modern-queue-date');
    const start=page.locator('.mqm-called-visits-list button');
    const startFor=(s)=>start.and(page.getByRole('button',{name:new RegExp(s)}));
    try {await startFor('OLD').waitFor();} catch(e){console.log((await page.locator('body').innerText()).slice(0,1200)); throw e;}
    await page.reload(); await startFor('OLD').waitFor();
    console.log('18:59Z: correct authenticated day and called ticket restored after reload');
    clock(after); await page.clock.setFixedTime(new Date(after));
    await projection(token,'2026-11-26',rows.CURRENT);
    await page.reload(); await startFor('CURRENT').waitFor();
    assert.equal(await start.count(),1);
    assert.equal(await date.inputValue(),'2026-11-26');
    assert.equal(await date.getAttribute('max'),'2026-11-26');
    await date.fill('2026-11-25');
    await start.waitFor({state:'hidden'});
    const call=page.locator('button[title="Backend call-next command"]');
    assert.equal(await date.inputValue(),'2026-11-25');
    assert.equal(await page.locator('.mqm-queue-load-error').count(),0);
    assert.equal(await call.isDisabled(),true);
    assert.equal(posts.length,0);
    await date.fill('2026-11-26'); await startFor('CURRENT').waitFor();
    await start.evaluate(el=>{el.click();el.click();});
    const output=page.getByLabel('Started synthetic visit');
    await page.waitForFunction(()=>document.querySelector('[aria-label="Started synthetic visit"]')?.textContent?.includes('"visit_id"'));
    const ack=JSON.parse(await output.textContent());
    assert.equal(ack.queue_entry_id,rows.CURRENT.entry);
    assert.equal(ack.patient_id,rows.CURRENT.patient);
    assert.equal(ack.visit_id,rows.CURRENT.visit);
    assert.deepEqual(posts,[String(rows.CURRENT.entry)]);
    await start.waitFor({state:'hidden'});
    await projection(token,'2026-11-26',rows.CURRENT,'in_progress');
    const other=await login('other');
    await projection(other,'2026-11-26',rows.OTHER);
    clock(before); await projection(token,'2026-11-25',rows.OLD); clock(after);
    console.log('19:00Z: correct clinic day, history read-only, one POST and correct linked visit, previous day and other doctor unchanged');
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
