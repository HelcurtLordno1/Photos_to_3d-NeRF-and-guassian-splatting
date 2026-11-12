import { createServer } from '../../../UI_design/node_modules/vite/dist/node/index.js';
import { chromium } from '../../../UI_design/node_modules/@playwright/test/index.mjs';
import { readFile,writeFile } from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const input=JSON.parse(await readFile(process.argv[2],'utf8'));
const root=fileURLToPath(new URL('../../../UI_design/',import.meta.url));
const assets=[input.ply,...input.native];
const server=await createServer({configFile:false,root,server:{host:'127.0.0.1',port:5177,strictPort:true},plugins:[{
  name:'owned-audit-assets',configureServer(server){server.middlewares.use((req,res,next)=>{
    const match=/^\/tea-assets\/(\d+)$/.exec(req.url||'');if(!match)return next();const file=assets[Number(match[1])];
    if(!file){res.statusCode=404;res.end();return;}res.setHeader('Content-Type',file.endsWith('.ply')?'application/octet-stream':'image/png');createReadStream(file).pipe(res);
  });}
}]});
await server.listen();let browser;
try {
  browser=await chromium.launch({executablePath:'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',headless:true,args:['--disable-background-timer-throttling']});
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:5177/qa/tea-parity.html');
  await page.waitForFunction(()=>typeof window.runTeaParity==='function');
  const output=await page.evaluate(job=>window.runTeaParity(job),{asset:'/tea-assets/0',cameras:input.cameras,native:input.native.map((_,i)=>'/tea-assets/'+(i+1))});
  for(const row of output.results){const file=path.join(input.output,row.preset+'-'+input.indices[row.index]+'.png');await writeFile(file,Buffer.from(row.png.split(',')[1],'base64'));row.image=file;delete row.png;row.eval_index=input.indices[row.index];}
  if(errors.length)throw new Error(errors.join('\n'));output.page_errors=errors;
  await writeFile(path.join(input.output,'browser-result.json'),JSON.stringify(output,null,2)+'\n');console.log(JSON.stringify(output,null,2));
} finally {if(browser)await browser.close();await server.close();}
