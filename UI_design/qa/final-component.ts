import React from 'react';
import { createRoot } from 'react-dom/client';
import FinalQuality from '../frontend/FinalQuality';
import type { Catalog, FinalScene } from '../frontend/types';

const catalog: Catalog = await (await fetch('/qa-catalog')).json();
const scene=catalog.scenes.find(s=>s.id==='custom:tea_sets_2')!;
const experiment=catalog.quality!.experiments.find(e=>e.scene===scene.id)!;
const historic=experiment.rows.find(r=>r.tag==='historical-native')!;
const candidate=catalog.visual_research!.q2!.rows.find(r=>r.method==='improvedgs')!;
const baseline=scene.methods.splatfacto;
const data:FinalScene={scene:scene.id,campaign:'existing-artifact-component-qa',cameras:candidate.model!.cameras,
  train_count:105,eval_count:15,models:{
    baseline:{label:'Existing baseline · native derivative',frames:historic.frames,metrics:historic.metrics,
      training_seconds:baseline.train_seconds,gaussians:baseline.vertices!,bytes:baseline.bytes,
      run:{...baseline,metrics:historic.metrics,background_rgb:[.149,.1647,.2157],rasterize_mode:'classic'}},
    upgrade:{label:'Existing v4 Improved-GS',frames:candidate.frames,metrics:candidate.metrics,
      training_seconds:candidate.training_seconds,gaussians:candidate.gaussians,bytes:candidate.model!.run.bytes,run:candidate.model!.run}},
  delta:{psnr:candidate.metrics.psnr-historic.metrics.psnr,ssim:candidate.metrics.ssim-historic.metrics.ssim,lpips:candidate.metrics.lpips-historic.metrics.lpips},
  per_view_delta:[],quality_dominates:true,preview_verdict:'existing-v4-measurement',scope:'QA fixture assembled from actual preserved baseline and v4 native images; not a new experiment.',
  report_url:'#',browser:{...catalog.visual_research!.inspection!.browser.find(b=>b.method==='improvedgs')!,parity_met:true,timing_met:true,scope:'Existing v5 P1 audit'},
  high_resolution:[],profile_notes:[]};
createRoot(document.getElementById('root')!).render(React.createElement(FinalQuality,{catalog,data,paused:false}));
