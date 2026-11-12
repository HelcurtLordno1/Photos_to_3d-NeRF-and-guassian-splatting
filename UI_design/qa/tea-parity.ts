import * as THREE from 'three';
import { SparkRenderer, SplatMesh } from '@sparkjsdev/spark';
import type { Camera } from '../frontend/types';

// Explicit calibration, independent of OrbitControls and responsive viewport sizes.
export function calibratedCamera(c: Camera) {
  const camera = new THREE.PerspectiveCamera();
  const m = c.camera_to_world;
  const world = new THREE.Matrix4().set(...[...m[0], ...m[1], ...m[2], 0, 0, 0, 1] as Parameters<THREE.Matrix4['set']>);
  world.decompose(camera.position, camera.quaternion, camera.scale);
  const n = .01, f = 200;
  camera.projectionMatrix.makePerspective(-c.cx*n/c.fx,(c.width-c.cx)*n/c.fx,c.cy*n/c.fy,-(c.height-c.cy)*n/c.fy,n,f);
  camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
  camera.updateMatrixWorld(true);return camera;
}

async function run(job: { asset: string; cameras: Camera[]; native: string[] }) {
  const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);renderer.outputColorSpace=THREE.SRGBColorSpace;
  // Match Splatfacto's fixed evaluation background, interpreted in output RGB space.
  const background = new THREE.Color().setRGB(.1490,.1647,.2157,THREE.SRGBColorSpace);
  renderer.setClearColor(background,1);document.body.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const spark = new SparkRenderer({renderer,autoUpdate:false,enableLod:false});scene.add(spark);
  const mesh = new SplatMesh({url:job.asset,lod:false,extSplats:true});scene.add(mesh);
  await mesh.initialized;
  const sh = mesh.splats?.getNumSh() ?? mesh.extSplats?.getNumSh() ?? mesh.packedSplats?.getNumSh() ?? 0;
  if(sh!==3) throw new Error('PLY SH degree was not preserved: '+sh);
  const results=[];
  for(let index=0;index<job.cameras.length;index++) {
    const c=job.cameras[index],camera=calibratedCamera(c);
    renderer.setSize(c.width,c.height,false);
    const image=await createImageBitmap(await (await fetch(job.native[index])).blob());
    const gt=document.createElement('canvas');gt.width=c.width;gt.height=c.height;
    const context=gt.getContext('2d')!;context.drawImage(image,0,0);const expected=context.getImageData(0,0,c.width,c.height).data;
    for(const preset of ['spark-default','classic-compatible'] as const) {
      spark.preBlurAmount=preset==='spark-default'?0:.3;
      spark.blurAmount=preset==='spark-default'?.3:0;
      spark.sortRadial=preset==='spark-default';
      await spark.update({scene,camera});renderer.render(scene,camera);
      const canvas=document.createElement('canvas');canvas.width=c.width;canvas.height=c.height;
      const ctx=canvas.getContext('2d')!;ctx.drawImage(renderer.domElement,0,0);const pixels=ctx.getImageData(0,0,c.width,c.height).data;
      let mse=0,mae=0;
      for(let p=0;p<pixels.length;p+=4)for(let ch=0;ch<3;ch++){const d=(pixels[p+ch]-expected[p+ch])/255;mse+=d*d;mae+=Math.abs(d);}
      const channels=c.width*c.height*3;
      results.push({index,preset,psnr:-10*Math.log10(Math.max(mse/channels,1e-12)),mae:mae/channels,png:canvas.toDataURL('image/png')});
    }
    image.close();
  }
  const gl=renderer.getContext();const debug=gl.getExtension('WEBGL_debug_renderer_info');
  const gpu=debug?gl.getParameter(debug.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);
  mesh.dispose();spark.dispose();renderer.dispose();renderer.forceContextLoss();renderer.domElement.remove();
  return {status:'passed',sh_degree:sh,gaussians:mesh.numSplats,renderer:gpu,results};
}
(window as unknown as {runTeaParity:typeof run}).runTeaParity=run;
