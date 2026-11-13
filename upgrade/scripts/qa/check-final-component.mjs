import {createServer} from '../../../UI_design/node_modules/vite/dist/node/index.js';
import {chromium} from '../../../UI_design/node_modules/@playwright/test/index.mjs';
import {readFile,writeFile} from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
const job=JSON.parse(await readFile(process.argv[2],'utf8'));
const payload=JSON.parse(await readFile(job.catalog,'utf8'));
const ui=fileURLToPath(new URL('../../../UI_design/',import.meta.url));
const server=await createServer({root:ui,configFile:path.join(ui,'vite.config.ts'),server:{host:'127.0.0.1',port:5179,strictPort:true},plugins:[{
  name:'owned-component-assets',configureServer(server){server.middlewares.use((req,res,next)=>{
    if(req.url==='/qa-catalog'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify(payload.catalog));return;}
    const match=/^\/api\/assets\/([a-f0-9]+)$/.exec(req.url||'');if(!match)return next();
    const item=payload.assets[match[1]];if(!item){res.statusCode=404;res.end();return;}
    const file=path.resolve(job.baseline,item.path),base=path.resolve(job.baseline)+path.sep;
    if(!file.toLowerCase().startsWith(base.toLowerCase())){res.statusCode=403;res.end();return;}
    res.setHeader('Content-Type',file.endsWith('.ply')?'application/octet-stream':'image/png');createReadStream(file).pipe(res);
  });}
}]});
await server.listen();let browser;const errors=[];
try {
  browser=await chromium.launch({executablePath:'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',headless:true,args:['--use-angle=d3d11']});
  const page=await browser.newPage({viewport:{width:1440,height:1000},locale:'en-US'});page.on('pageerror',e=>errors.push(e.message));
  const downloads=new Map();page.on('request',r=>downloads.set(r.url(),(downloads.get(r.url())||0)+1));
  await page.goto('http://127.0.0.1:5179/qa/final-component.html');await page.getByLabel('Final model',{exact:true}).waitFor();
  assert.equal(await page.getByLabel('Final model',{exact:true}).inputValue(),'upgrade');
  assert.equal(await page.locator('img[data-final-image]').count(),2);
  await page.waitForFunction(()=>[...document.querySelectorAll('img[data-final-image]')].every(im=>im.complete&&im.naturalWidth===719));
  const results=[];
  await page.getByRole('button',{name:'Explore selected 3D',exact:true}).click();
  for(const [model,count] of [['upgrade',300000],['baseline',payload.catalog.scenes.find(s=>s.id==='custom:tea_sets_2').methods.splatfacto.vertices]]) {
    await page.getByLabel('Final model',{exact:true}).selectOption(model);
    const open=page.getByRole('button',{name:'Open selected 3D',exact:true});if(await open.count())await open.click();
    await page.getByText(count.toLocaleString('en-US')+' Gaussian · ready',{exact:true}).waitFor({timeout:120000});
    const canvas=page.locator('[data-final-scene] canvas').last();await canvas.scrollIntoViewIfNeeded();await page.waitForTimeout(2000);
    const before=await canvas.getAttribute('data-render-count');await page.waitForTimeout(1200);assert.equal(await canvas.getAttribute('data-render-count'),before);
    const plyRequests=[...downloads].filter(([url])=>url.includes('/api/assets/')).map(([url,n])=>[url,n]);
    const next=(await page.getByLabel('Final view',{exact:true}).inputValue())==='8'?'0':'8';
    await page.getByLabel('Final view',{exact:true}).selectOption(next);await page.waitForTimeout(500);
    assert.ok(Number(await canvas.getAttribute('data-render-count'))>Number(before),model+' camera preset did not draw');
    // Native image URLs may change; the selected PLY must remain downloaded once.
    const ply=model==='upgrade'?payload.catalog.visual_research.q2.rows.find(r=>r.method==='improvedgs').model.run.asset:
      payload.catalog.scenes.find(s=>s.id==='custom:tea_sets_2').methods.splatfacto.asset;
    const url='http://127.0.0.1:5179'+ply,old=plyRequests.find(([key])=>key===url)?.[1];assert.ok(old>=1);assert.equal(downloads.get(url),old);
    results.push({model,vertices:count,idle_draws:before,camera_change_without_ply_reload:true});
    await page.getByRole('button',{name:'Close selected 3D',exact:true}).click();
  }
  assert.equal(errors.length,0,errors.join('\n'));await page.screenshot({path:path.join(job.output,'component.png'),fullPage:true});
  await writeFile(path.join(job.output,'component-check.json'),JSON.stringify({status:'passed',scope:'UI component integration with real existing Tea baseline/v4 weights and saved images only. Not new campaign quality evidence.',results,page_errors:errors},null,2));
} finally {if(browser)await browser.close();await server.close();}
