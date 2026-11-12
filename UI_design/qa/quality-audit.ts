import * as THREE from 'three';
import { SparkRenderer, SplatMesh } from '@sparkjsdev/spark';
import type { Camera } from '../frontend/types';
import { calibratedCamera } from './tea-parity';

type Job = { asset: string; cameras: Camera[]; native: string[]; orbit: Camera[]; encoding?: 'packed'|'ext32'|'ext32-full'|'packed-ext' };
async function run(job: Job) {
  const renderer=new THREE.WebGLRenderer({antialias:false,preserveDrawingBuffer:true});
  renderer.setPixelRatio(1);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.setClearColor(0,1);
  document.body.appendChild(renderer.domElement);
  const scene=new THREE.Scene();
  const spark=new SparkRenderer({renderer,autoUpdate:false,enableLod:false,preBlurAmount:.3,blurAmount:0,sortRadial:false,minSortIntervalMs:0,
    accumExtSplats:job.encoding==='ext32-full'||job.encoding==='packed-ext'});scene.add(spark);
  const mesh=new SplatMesh({url:job.asset,lod:false,extSplats:job.encoding?.startsWith('ext32')});scene.add(mesh);await mesh.initialized;
  const sh=mesh.splats?.getNumSh()??mesh.extSplats?.getNumSh()??mesh.packedSplats?.getNumSh()??0;
  if(sh!==3)throw new Error('Production packed PLY SH degree differs');
  const results=[];
  for(let i=0;i<job.cameras.length;i++) {
    const c=job.cameras[i],camera=calibratedCamera(c);renderer.setSize(c.width,c.height,false);
    await spark.update({scene,camera});renderer.render(scene,camera);
    const expectedImage=await createImageBitmap(await(await fetch(job.native[i])).blob());
    const canvas=document.createElement('canvas');canvas.width=c.width;canvas.height=c.height;
    const context=canvas.getContext('2d')!;context.drawImage(expectedImage,0,0);
    const expected=context.getImageData(0,0,c.width,c.height).data;
    context.drawImage(renderer.domElement,0,0);const actual=context.getImageData(0,0,c.width,c.height).data;
    let mse=0;for(let p=0;p<actual.length;p+=4)for(let k=0;k<3;k++)mse+=((actual[p+k]-expected[p+k])/255)**2;
    results.push({view:i,psnr:-10*Math.log10(Math.max(mse/(c.width*c.height*3),1e-12)),png:canvas.toDataURL('image/png')});expectedImage.close();
  }
  const durations:number[]=[],intervals:number[]=[];let previous=0;renderer.setSize(1280,720,false);
  for(let i=0;i<210;i++) {
    await new Promise<void>(resolve=>requestAnimationFrame(()=>resolve()));
    const frameStart=performance.now();if(i>=30)intervals.push(frameStart-previous);previous=frameStart;
    const phase=i%(2*job.orbit.length-2);const source=job.orbit[phase<job.orbit.length?phase:2*job.orbit.length-2-phase];const ratio=720/source.height;
    const c={...source,width:1280,height:720,fx:source.fx*ratio,fy:source.fy*ratio,
      cx:640+(source.cx-source.width/2)*ratio,cy:360+(source.cy-source.height/2)*ratio};
    const camera=calibratedCamera(c),start=performance.now();
    await spark.update({scene,camera});renderer.render(scene,camera);renderer.getContext().finish();
    if(i>=30)durations.push(performance.now()-start);
  }
  const sorted=[...durations].sort((a,b)=>a-b),sortedIntervals=[...intervals].sort((a,b)=>a-b),gl=renderer.getContext(),debug=gl.getExtension('WEBGL_debug_renderer_info');
  const result={status:'measured',sh_degree:sh,gaussians:mesh.numSplats,coordinate_encoding:job.encoding||'production-packed',
    renderer:debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),results,
    benchmark:{width:1280,height:720,dpr:1,lod:false,warmup_frames:30,measured_frames:180,
      median_ms:sorted[Math.floor(sorted.length*.5)],p95_ms:sorted[Math.ceil(sorted.length*.95)-1],durations_ms:durations,
      p95_frame_interval_ms:sortedIntervals[Math.ceil(sortedIntervals.length*.95)-1],frame_intervals_ms:intervals,
      scope:'Sorted moving-camera render with gl.finish. Service time excludes RAF waiting; frame intervals include RAF waiting. No physical display scanout or browser-wide FPS claim.'}};
  mesh.dispose();spark.dispose();renderer.dispose();renderer.forceContextLoss();renderer.domElement.remove();return result;
}
(window as unknown as {runQualityAudit:typeof run}).runQualityAudit=run;
