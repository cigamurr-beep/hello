// usage: node render.js video.html outDir fps [t1,t2,...]
const { chromium } = require('playwright');
const path=require('path'),fs=require('fs');
(async()=>{
  const [,,html,out,fpsS,list]=process.argv; const fps=+fpsS||30;
  fs.mkdirSync(out,{recursive:true});
  const b=await chromium.launch(); const p=await b.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});
  await p.goto('file://'+path.resolve(html)); await p.waitForTimeout(400);
  const total=await p.evaluate(()=>window.TOTAL);
  const times=list? list.split(',').map(Number) : Array.from({length:Math.ceil(total*fps)},(_,i)=>i/fps);
  for(let i=0;i<times.length;i++){
    await p.evaluate(t=>window.render(t),times[i]);
    await p.screenshot({path:`${out}/f${String(i).padStart(5,'0')}.${list?'png':'jpg'}`,...(list?{}:{type:'jpeg',quality:92})});
    if(i%150===0) console.log('frame',i,'/',times.length);
  }
  await b.close();
})();
