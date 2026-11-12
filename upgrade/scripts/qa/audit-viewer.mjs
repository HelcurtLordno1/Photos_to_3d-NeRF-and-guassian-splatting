import {createServer} from '../../../UI_design/node_modules/vite/dist/node/index.js';
import {chromium} from '../../../UI_design/node_modules/@playwright/test/index.mjs';
import {readFile,writeFile} from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const input=JSON.parse(await readFile(process.argv[2],'utf8'));
const assets=[input.ply,...input.native];
const server=await createServer({configFile:false,root:fileURLToPath(new URL('../../../UI_design/',import.meta.url)),server:{host:'127.0.0.1',port:5178,strictPort:true},plugins:[{
 name:'audit-assets',configureServer(server){server.middlewares.use((req,res,next)=>{
 const match=/^\/audit-assets\/(\d+)$/.exec(req.url||'');if(!match)return next();const file=assets[Number(match[1])];
 if(!file){res.statusCode=404;res.end();return;}res.setHeader('Content-Type',file.endsWith('.ply')?'application/octet-stream':'image/png');createReadStream(file).pipe(res);
 });}
}]});
await server.listen();let browser;
try {
 browser=await chromium.launch({executablePath:'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',headless:true,args:['--use-angle=d3d11','--disable-background-timer-throttling']});
 const page=await browser.newPage({viewport:{width:1440,height:1440}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:5178/qa/quality-audit.html');await page.waitForFunction(()=>typeof window.runQualityAudit==='function');
 const output=await page.evaluate(job=>window.runQualityAudit(job),{asset:'/audit-assets/0',cameras:input.cameras,native:input.native.map((_,i)=>'/audit-assets/'+(i+1)),orbit:input.orbit,encoding:input.encoding});
 for(const row of output.results){const file=path.join(input.output,'spark-'+row.view+'.png');await writeFile(file,Buffer.from(row.png.split(',')[1],'base64'));row.file=file;delete row.png;}
 if(errors.length)throw new Error(errors.join('\n'));output.page_errors=errors;
 await writeFile(path.join(input.output,'browser-result.json'),JSON.stringify(output,null,2));console.log('Packed renderer audit complete: '+output.renderer);
} finally {if(browser)await browser.close();await server.close();}
