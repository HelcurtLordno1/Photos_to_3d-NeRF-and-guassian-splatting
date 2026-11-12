import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
const job=JSON.parse(await readFile(process.argv[2],'utf8'));
await mkdir(job.output,{recursive:true});
const browser=await chromium.launch({executablePath:'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',headless:true,args:['--use-angle=d3d11']});
const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1,locale:'en-US'}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
const results=[];
const requests=new Map();page.on('request',r=>requests.set(r.url(),(requests.get(r.url())||0)+1));
try {
  await page.addInitScript(()=>localStorage.setItem('topic16-onboarded','1'));
  for(const scene of job.scenes) {
    await page.goto(job.url+'/');
    await page.locator('button').filter({hasText:scene.title}).first().click();
    await page.locator('[data-final-scene]').waitFor();
    assert.equal(await page.locator('[data-final-scene]').getAttribute('data-final-scene'),scene.scene);
    assert.equal(await page.getByLabel('Final model',{exact:true}).inputValue(),'upgrade');
    const index=Math.floor(scene.cameras.length/2);
    await page.getByLabel('Final view',{exact:true}).selectOption(String(index));
    assert.equal(await page.locator('img[data-final-image]').count(),3);
    await page.waitForFunction(width=>[...document.querySelectorAll('img[data-final-image]')].every(im=>im.complete&&im.naturalWidth===width),scene.cameras[index].width);
    const models=[];
    for(const model of ['upgrade','baseline']) {
      await page.getByLabel('Final model',{exact:true}).selectOption(model);
      const row=page.getByRole('table',{name:'Final benchmark'}).locator('tr[aria-selected="true"]');
      assert.match(await row.innerText(),new RegExp(scene.models[model].metrics.psnr.toFixed(4).replace('.','\\.')));
      const started=performance.now();await page.getByRole('button',{name:'Open selected 3D',exact:true}).click();
      await page.getByText(scene.models[model].gaussians.toLocaleString('en-US')+' Gaussian · ready',{exact:true}).waitFor({timeout:180000});
      const canvas=page.locator('[data-final-scene] canvas').last();await canvas.scrollIntoViewIfNeeded();
      const loadMs=performance.now()-started;
      await page.waitForTimeout(2000);const before=Number(await canvas.getAttribute('data-render-count'));
      await page.waitForTimeout(1200);const after=Number(await canvas.getAttribute('data-render-count'));
      assert.ok(before>0);assert.equal(after,before,'Idle selected model continues drawing');
      const box=await canvas.boundingBox();assert.ok(box&&box.width>0);
      await page.mouse.move(box.x+box.width*.45,box.y+box.height*.5);await page.mouse.down();
      await page.mouse.move(box.x+box.width*.55,box.y+box.height*.5,{steps:8});await page.mouse.up();
      await page.waitForTimeout(500);assert.ok(Number(await canvas.getAttribute('data-render-count'))>after);
      const asset=new URL(scene.models[model].run.asset,job.url).href;
      const downloads=requests.get(asset)||0;
      assert.ok(downloads>=1,'Real PLY request was not observed');
      await page.getByLabel('Final view',{exact:true}).selectOption('0');
      await page.waitForTimeout(500);
      assert.equal(requests.get(asset)||0,downloads,'Changing a saved camera re-downloads the PLY');
      await page.getByLabel('Final view',{exact:true}).selectOption(String(index));
      models.push({model,vertices:scene.models[model].gaussians,load_ms:loadMs,idle:{before,after},drag:'passed',
        canvas:await canvas.evaluate(c=>({width:c.width,height:c.height}))});
      await page.getByRole('button',{name:'Close selected 3D',exact:true}).click();
      await page.locator('[data-final-scene] canvas').waitFor({state:'detached'});
    }
    const profiles=[];
    for(const edge of [3840,7680]) {
      const frames=scene.high_resolution.filter(p=>p.edge===edge&&p.view===0);
      if(!frames.length){profiles.push({edge,status:'unsupported-as-declared'});continue;}
      await page.getByLabel('Final output',{exact:true}).selectOption(String(edge));
      assert.equal(await page.locator('img[data-final-image]').count(),frames.length);
      await page.waitForFunction(width=>[...document.querySelectorAll('img[data-final-image]')].every(im=>im.complete&&im.naturalWidth===width),frames[0].width,{timeout:120000});
      assert.ok((await page.getByRole('table',{name:'Final benchmark'}).innerText()).includes(scene.models.upgrade.metrics.psnr.toFixed(4)));
      profiles.push({edge,status:'loaded',width:frames[0].width,height:frames[0].height});
    }
    await page.getByLabel('Final output',{exact:true}).selectOption('0');
    await page.screenshot({path:path.join(job.output,scene.scene.replace(':','-')+'.png'),fullPage:true});
    results.push({scene:scene.scene,status:'passed',models,profiles});
  }
  assert.equal(errors.length,0,errors.join('\n'));
  await writeFile(path.join(job.output,'browser-check.json'),JSON.stringify({status:'passed',scenes:results,page_errors:errors,
    scope:'Actual fresh navigation, native GT/model/metrics, both real PLYs, idle/drag and available4K/8K images. Load times are descriptive, not fixed-profile FPS or total VRAM.',checked_at:new Date().toISOString()},null,2));
} finally {await browser.close();}
