import { chromium } from '@playwright/test';
import { spawn, execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { mkdir,writeFile } from 'node:fs/promises';
import path from 'node:path';
const root=fileURLToPath(new URL('../../',import.meta.url));
const output=path.join(root,'artifacts/ui/qa/spike');await mkdir(output,{recursive:true});
const server=spawn(process.argv[2], [path.join(root,'UI_design/spike/serve.py')],{stdio:'inherit'});
const samples=[];const sample=()=>{try {return execFileSync('nvidia-smi',['--query-gpu=memory.used,temperature.gpu,power.draw','--format=csv,noheader'],{encoding:'utf8'}).trim()}catch{return null}};
samples.push({phase:'before',gpu:sample()});
let browser;
try {
  for(let i=0;i<30;i++){try{const r=await fetch('http://127.0.0.1:7015');if(r.ok)break;}catch{} await new Promise(r=>setTimeout(r,300));}
  browser=await chromium.launch({executablePath:'C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe',headless:true});
  const page=await browser.newPage({viewport:{width:1366,height:768}});
  const workers=[];page.on('worker',w=>workers.push(w.url()));
  page.on('console',m=>{if(m.type()==='error')console.log('BROWSER ERROR',m.text())});
  const results=[];
  for(const scene of ['custom:tea_sets_2','garden']){
    console.log('Loading actual Gaussian:',scene);
    await page.goto('http://127.0.0.1:7015/?scene='+encodeURIComponent(scene));
    await page.waitForFunction(()=>window.__spike?.ready || window.__spike?.error,{},{timeout:180000});
    const record=await page.evaluate(()=>window.__spike);record.worker_urls=[...workers];
    if(record.error)throw new Error(record.error);
    await page.waitForTimeout(2000);record.memory=await page.evaluate(()=>performance.memory ? {used:performance.memory.usedJSHeapSize,total:performance.memory.totalJSHeapSize}:null);
    await page.screenshot({path:path.join(output,scene.replace(':','-')+'.png')});
    samples.push({phase:scene,gpu:sample()});results.push({scene,...record});console.log(JSON.stringify(record));
  }
  await writeFile(path.join(output,'native-spark.json'),JSON.stringify({browser:await browser.version(),results,samples},null,2));
} finally {await browser?.close();server.kill();}
