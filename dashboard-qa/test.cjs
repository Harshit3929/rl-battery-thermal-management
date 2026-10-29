const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

(async () => {
  const out = path.resolve(__dirname, '../report/dashboard/screenshots');
  await fs.mkdir(out, {recursive:true});
  const browser = await chromium.launch({channel:'msedge', headless:true});
  const page = await browser.newPage({viewport:{width:1440,height:1100}, deviceScaleFactor:1});
  page.setDefaultTimeout(180000);
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  try {
    console.log('Opening local dashboard');
    await page.route('https://fonts.googleapis.com/**',route=>route.abort());
    await page.goto('http://127.0.0.1:8765', {waitUntil:'domcontentloaded'});
    await page.waitForFunction(() => document.querySelector('#backend-label').textContent.includes('connected'));
    assert.equal(await page.locator('#run').isEnabled(), true);
    assert.equal(await page.locator('#battery-pack .battery-node strong').first().innerText(), '—°C');
    console.log('Running a fresh SAC + PID simulation');
    await page.locator('#run').click();
    await page.waitForFunction(() => document.querySelector('#run-mode').textContent === 'FRESH RUN COMPLETE', null, {timeout:180000});
    assert.equal(await page.locator('#run-comparison tbody tr').count(), 2);
    assert.equal(await page.locator('#run-comparison .pill').filter({hasText:'MATCH'}).count(), 2);
    await page.locator('#timeline').evaluate(el => {el.value=el.max; el.dispatchEvent(new Event('input'));});
    assert.match(await page.locator('#time-value').innerText(), /1,800/);
    console.log('Capturing screenshot');
    await page.screenshot({timeout:30000,animations:'disabled',path:path.join(out,'simulation-desktop.png'),fullPage:true});
    const downloadEvent = page.waitForEvent('download');
    await page.locator('#export-run').click();
    const downloaded = await downloadEvent;
    await downloaded.saveAs(path.join(out,'browser-exported-run.json'));
    const payload=JSON.parse(await fs.readFile(path.join(out,'browser-exported-run.json'),'utf8'));
    assert.equal(payload.results[0].kind,'fresh simulation');
    assert.equal(payload.results[0].trace.length,361);
    assert.equal(payload.results[0].metrics.duration_s,1800);
    console.log('Verifying results, training and evidence views');
    await page.locator('[data-view="results"]').click();
    assert.equal(await page.locator('#comparison-table tbody tr').count(),7);
    await page.locator('#show-raw').click();
    assert.match(await page.locator('#comparison-table').innerText(), /41\.15/);
    console.log('Capturing screenshot');
    await page.screenshot({timeout:30000,animations:'disabled',path:path.join(out,'results-desktop.png'),fullPage:true});
    await page.locator('[data-view="training"]').click();
    assert.equal(await page.locator('#training-table tbody tr').count(),15);
    assert.equal(await page.locator('#training-chart svg').count(),1);
    console.log('Capturing screenshot');
    await page.screenshot({timeout:30000,animations:'disabled',path:path.join(out,'training-desktop.png'),fullPage:true});
    await page.locator('[data-view="evidence"]').click();
    assert.match(await page.locator('#audit-summary').innerText(), /6 \/ 6/);
    await page.locator('#artifact-search').fill('IEEE_BTMS_Manuscript');
    assert.equal(await page.locator('#artifacts tbody tr').count(),1);
    const sourceLink=await page.locator('#artifacts tbody a').getAttribute('href');
    const response=await page.request.get(new URL(sourceLink,page.url()).href);
    assert.equal(response.ok(),true);
    assert.match(await response.text(),/documentclass/);
    await page.locator('#artifact-search').fill('');
    console.log('Capturing screenshot');
    await page.screenshot({timeout:30000,animations:'disabled',path:path.join(out,'evidence-desktop.png'),fullPage:true});
    console.log('Verifying mobile layout');
    await page.setViewportSize({width:390,height:844});
    await page.locator('[data-view="simulation"]').click();
    const overflow=await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    console.log('Capturing screenshot');
    await page.screenshot({timeout:30000,animations:'disabled',path:path.join(out,'simulation-mobile.png'),fullPage:true});
    if(overflow)console.log(await page.evaluate(()=>Array.from(document.querySelectorAll('body *')).filter(e=>e.getBoundingClientRect().right>innerWidth+1&&!e.closest('[hidden]')).slice(0,20).map(e=>({tag:e.tagName,id:e.id,class:e.className,right:e.getBoundingClientRect().right}))));
    assert.equal(overflow,false,'Mobile document should not overflow horizontally');
    assert.deepEqual(errors,[]);
    const report={completed_at:new Date().toISOString(),status:'passed',browser:'Installed Microsoft Edge, headless Playwright',
      checks:['initial state contains no invented measurements','fresh SAC + PID simulations complete','download contains actual traces and provenance',
        'seven-controller tables and raw mode','15 training runs and actual event curves','paper audit and allowlisted manuscript download',
        'mobile viewport without document overflow','no page JavaScript errors'],screenshots:out};
    await fs.writeFile(path.resolve(__dirname,'../report/dashboard/browser_test.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report,null,2));
  } finally {
    await browser.close();
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
