const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  const page=await browser.newPage({viewport:{width:1400,height:1000}});
  page.setDefaultTimeout(60000);
  try{
    await page.goto('http://127.0.0.1:8766',{waitUntil:'domcontentloaded'});
    await page.waitForSelector('#saved-replays button');
    assert.equal(await page.locator('#run').isDisabled(),true);
    assert.equal(await page.locator('#snapshot-notice').isVisible(),true);
    const buttons=page.locator('#saved-replays button');
    assert.equal(await buttons.count(),8);
    await buttons.first().click();
    await page.waitForFunction(()=>document.querySelector('#run-mode').textContent==='RECORDED RUN REPLAY');
    assert.match(await page.locator('#run-comparison').innerText(),/MATCH/);
    await page.locator('[data-view="evidence"]').click();
    assert.match(await page.locator('#test-status').innerText(),/TEST COMMAND PASSED/);
    assert.match(await page.locator('#reproduction-status').innerText(),/COMPLETED CHECKS MATCH/);
    assert.match(await page.locator('#reproduction-status').innerText(),/288/);
    const report={completed_at:new Date().toISOString(),status:'passed',
      checks:['static viewer explicitly disables fresh Python simulation','eight actual exported rollouts available',
        'replays labeled as recorded data','captured tests and completed 288-case reproduction visible']};
    await fs.writeFile(path.resolve(__dirname,'../report/dashboard/static_test.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report,null,2));
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
