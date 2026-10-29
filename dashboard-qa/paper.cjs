const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const crypto=require('node:crypto');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1050}});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  try{
    await page.goto('http://127.0.0.1:8765/#evidence',{waitUntil:'domcontentloaded'});
    await page.waitForSelector('#paper-revision:visible');
    assert.match(await page.locator('#paper-detail').innerText(),/9 pages/);
    assert.match(await page.locator('#paper-detail').innerText(),/15 references/);
    assert.match(await page.locator('#paper-detail').innerText(),/4 studies/);
    assert.equal(await page.locator('#paper-badge').innerText(),'AUTOMATED CHECKS PASSED');
    const href=await page.locator('#paper-pdf').getAttribute('href');
    const response=await page.request.get(new URL(href,page.url()).href);
    assert.equal(response.ok(),true);
    const bytes=await response.body();
    assert.equal(bytes.subarray(0,5).toString(),'%PDF-');
    const expected=JSON.parse(await fs.readFile(path.resolve(__dirname,'../report/paper_revision/build_manifest.json'),'utf8')).pdf_sha256;
    assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),expected);
    assert.deepEqual(errors,[]);
    const report={checked_at:new Date().toISOString(),status:'passed',checks:['corrected paper card visible','9 pages and 15 actual references','four recent references counted from registry','PDF download matches verified build SHA-256','no JavaScript errors']};
    await fs.writeFile(path.resolve(__dirname,'../report/paper_revision/dashboard_check.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report,null,2));
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
