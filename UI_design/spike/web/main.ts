import * as THREE from 'three';
import { SplatMesh, SparkRenderer } from '@sparkjsdev/spark';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
const canvas = document.getElementById('canvas') as HTMLCanvasElement;
const renderer = new THREE.WebGLRenderer({canvas, antialias:false, powerPreference:'high-performance'});
renderer.setSize(innerWidth,innerHeight); renderer.setPixelRatio(1);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(60,innerWidth/innerHeight,0.01,100);
camera.up.set(0,0,1); camera.position.set(2,2,1.5);
const controls = new OrbitControls(camera,canvas);controls.enableDamping=true;
const spark = new SparkRenderer({renderer});scene.add(spark);
const gl = renderer.getContext();const debug = gl.getExtension('WEBGL_debug_renderer_info');
const metrics: Record<string,unknown> = {ready:false,workers:0,gpu:debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER), frames:0};
(window as any).__spike = metrics;
const query = new URLSearchParams(location.search);const sceneId = query.get('scene') || 'custom:tea_sets_2';
const started=performance.now();
const splats=new SplatMesh({url:'/asset/'+encodeURIComponent(sceneId+'-splatfacto'),onProgress:(e:ProgressEvent)=>{
  document.getElementById('status')!.textContent=`${sceneId}: ${Math.round(e.loaded/1048576)} MiB`;
}});scene.add(splats);
splats.initialized.then(()=>{
  const box=splats.getBoundingBox();const center=box.getCenter(new THREE.Vector3());
  controls.target.copy(center); const radius=Math.min(10,Math.max(.5,box.getSize(new THREE.Vector3()).length()*.12));
  camera.position.copy(center).add(new THREE.Vector3(radius,radius,radius*.7));controls.update();
  metrics.ready=true;metrics.load_ms=performance.now()-started;metrics.splats=splats.numSplats;
  document.getElementById('status')!.textContent=`${sceneId} · ${splats.numSplats.toLocaleString()} Gaussian · ${Math.round(Number(metrics.load_ms))} ms`;
}).catch((e:unknown)=>{metrics.error=String(e);document.getElementById('status')!.textContent=String(e)});
renderer.setAnimationLoop(()=>{controls.update();renderer.render(scene,camera);metrics.frames=Number(metrics.frames)+1;});
