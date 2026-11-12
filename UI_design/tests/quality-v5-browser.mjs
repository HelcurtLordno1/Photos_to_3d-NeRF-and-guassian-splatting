import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const root=new URL('../../upgrade/reports/tea-quality-v5/ui/',import.meta.url);await mkdir(root,{recursive:true});
const browser=await chromium.launch({executablePath:'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',headless:true,args:['--use-angle=d3d11']});
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
try {
 await page.addInitScript(()=>localStorage.setItem('topic16-onboarded','1'));
 await page.goto('http://127.0.0.1:7016/');
 await page.locator('button').filter({hasText:/tea sets/i}).first().click();
 await page.getByLabel('Quality model',{exact:true}).waitFor();
 assert.equal(await page.getByLabel('Quality model',{exact:true}).inputValue(),'improvedgs');
 await page.goto('http://127.0.0.1:7016/?scene=custom%3Atea_sets_2&tab=quality');
 await page.getByLabel('Quality model',{exact:true}).waitFor();assert.equal(await page.getByLabel('Quality model',{exact:true}).inputValue(),'improvedgs');
 await page.getByLabel('Quality view').selectOption('8');
 await page.waitForFunction(()=>[...document.querySelectorAll('figure img')].every(x=>x.complete&&x.naturalWidth===719));
 assert.match(await page.getByRole('table',{name:'Quality benchmark'}).innerText(),/31\.7343/);
 await page.getByLabel('Quality model',{exact:true}).selectOption('q1');
 assert.match(await page.getByRole('table',{name:'Quality benchmark'}).locator('tr[aria-selected="true"]').innerText(),/30\.4228/);
 await page.getByLabel('Quality resolution').selectOption('half');
 await page.waitForFunction(()=>[...document.querySelectorAll('figure img')].every(x=>x.complete&&x.naturalWidth===359));
 await page.getByLabel('Quality model',{exact:true}).selectOption('improvedgs');
 const pending=page.getByText(/no verified saved images at the selected output/);
 if(await pending.count()===0)await page.waitForFunction(()=>[...document.querySelectorAll('figure img')].every(x=>x.complete&&x.naturalWidth===359));
 await page.getByLabel('Quality resolution').selectOption('native');
 await page.screenshot({path:fileURLToPath(new URL('selected-q2.png',root)),fullPage:true});
 let idle=null,load=null;
 if(!process.argv.includes('--no-3d')) {
   const started=performance.now();
   await page.getByRole('button',{name:'Open improvedgs 3D',exact:true}).click();
   await page.getByText('300,000 Gaussian · ready',{exact:true}).waitFor({timeout:120000});
   const canvas=page.locator('canvas').last();await canvas.scrollIntoViewIfNeeded();
   load={time_to_ready_ms:performance.now()-started,canvas:await canvas.evaluate(c=>({width:c.width,height:c.height})),
     scope:'Local interactive UI click to ready, including module/download/decode. Not the fixed benchmark viewport or total GPU memory.'};
   await page.waitForTimeout(2000);const before=await canvas.getAttribute('data-render-count');
   await page.waitForTimeout(1500);const after=await canvas.getAttribute('data-render-count');
   assert.equal(after,before,'Idle viewer keeps drawing');idle={before,after};
   const box=await canvas.boundingBox();await page.mouse.move(box.x+box.width*.5,box.y+box.height*.5);await page.mouse.down();await page.mouse.move(box.x+box.width*.6,box.y+box.height*.5,{steps:12});await page.mouse.up();
   await page.waitForTimeout(500);assert.ok(Number(await canvas.getAttribute('data-render-count'))>Number(after));
   await page.screenshot({path:fileURLToPath(new URL('q2-on-demand.png',root)),fullPage:true});
 }
 assert.equal(errors.length,0,errors.join('\n'));
 await writeFile(new URL(process.argv.includes('--no-3d')?'images-check.json':'browser-check.json',root),JSON.stringify({status:'passed',errors,idle,load,checked_at:new Date().toISOString(),scope:'Unified model selection controls GT/pred/benchmark/3D; selectedQ2 default; half evidence uses its own resolution; idle render and drag checked when enabled.'},null,2));
} finally {await browser.close();}
