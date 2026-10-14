const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
(async () => {
  const browser = await chromium.launch({headless: true});
  let passed = 0;
  try {
    for (const scenario of [
      {name:'directory via case studies', referrer:'https://hypestar.org/project/8bitconcepts', via:true, expected:'hypestar'},
      {name:'second directory', referrer:'https://getservices.ai/marketplace/experts/8bitconcepts-agency', expected:'getservices'},
      {name:'explicit campaign wins', query:'?utm_source=partner&utm_medium=referral&utm_campaign=consulting', referrer:'https://hypestar.org/', expected:'partner'},
      {name:'LinkedIn preserved', query:'?utm_source=linkedin&utm_medium=qlimit&qc=example-campaign', expected:'linkedin', source:'8bitconcepts-linkedin-qlimit'},
      {name:'direct remains unattributed'},
      {name:'unknown referrer clears earlier campaign', query:'?utm_source=partner', nextReferrer:'https://example.org/'},
      {name:'private query excluded', query:'?utm_source=person%40example.org&email=private%40example.org'},
      {name:'unavailable storage keeps direct form tags', query:'?utm_source=partner', storageBlocked:true, directForm:true, expected:'partner'},
      {name:'failure retains entered inquiry', referrer:'https://hypestar.org/', expected:'hypestar', fail:true}
    ]) {
      const context = await browser.newContext();
      if (scenario.storageBlocked) await context.addInitScript(() => Object.defineProperty(window, 'sessionStorage', {get(){throw Error('storage disabled');}}));
      let body;
      await context.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.hostname === 'aidevboard.com' && url.pathname === '/api/v1/lead') {
          body = route.request().postDataJSON();
          return route.fulfill({status:scenario.fail ? 503 : 200, contentType:'application/json', body:scenario.fail ? '{"error":"unavailable"}' : '{"ok":true}', headers:{'access-control-allow-origin':'*'}});
        }
        if (url.hostname !== '8bitconcepts.test') return route.abort();
        const file = path.resolve(root, '.' + (url.pathname === '/' ? '/index.html' : url.pathname));
        if (!file.startsWith(root + path.sep) || !fs.existsSync(file)) return route.fulfill({status:404,body:'Not found'});
        return route.fulfill({status:200,contentType:file.endsWith('.js')?'text/javascript':file.endsWith('.svg')?'image/svg+xml':'text/html',body:fs.readFileSync(file)});
      });
      const page = await context.newPage();
      await page.goto('https://8bitconcepts.test/' + (scenario.directForm?'work-with-us.html':'') + (scenario.query || ''), scenario.referrer ? {referer:scenario.referrer}:{});
      if (scenario.via) await page.locator('nav a[href="/case-studies.html"]').click();
      if (!scenario.directForm) await page.goto('https://8bitconcepts.test/work-with-us.html', {referer:scenario.nextReferrer || 'https://8bitconcepts.test/'});
      await page.locator('input[name="name"]').fill('Browser verification');
      await page.locator('input[name="email"]').fill('browser@example.invalid');
      await page.locator('textarea[name="message"]').fill('Verify attribution without a real inquiry.');
      await page.locator('#lead-form-el button').click();
      await page.waitForFunction(() => !document.querySelector('#lead-status').textContent.includes('Sending'));
      assert.ok(body, scenario.name + ': request was intercepted');
      assert.equal(body.utm_source, scenario.expected, scenario.name);
      assert.equal(body.source, scenario.source || '8bitconcepts-work-with-us');
      assert.equal(body.email, 'browser@example.invalid');
      assert.ok(!JSON.stringify(body).includes('private@example.org'));
      if (scenario.fail) {
        assert.match(await page.locator('#lead-status').innerText(), /Error/);
        assert.equal(await page.locator('input[name="name"]').inputValue(), 'Browser verification');
        assert.equal(await page.locator('#lead-form-el button').isDisabled(), false);
      } else assert.match(await page.locator('#lead-status').innerText(), /Got it/);
      if (scenario.name === 'direct remains unattributed' && process.env.QA_DIR) {
        fs.mkdirSync(process.env.QA_DIR,{recursive:true});
        for (const [name,width,height] of [['desktop',1440,1000],['mobile',390,844]]) {
          await page.setViewportSize({width,height}); await page.screenshot({path:path.join(process.env.QA_DIR,`inquiry-${name}.png`),fullPage:true});
          await page.goto('https://8bitconcepts.test/'); await page.screenshot({path:path.join(process.env.QA_DIR,`home-${name}.png`),fullPage:true});
          await page.goto('https://8bitconcepts.test/work-with-us.html');
        }
      }
      passed++; await context.close();
    }
    console.log(`${passed} browser scenarios passed; all external requests intercepted.`);
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
