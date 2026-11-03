import { chromium } from "playwright";
const SC="/tmp/claude-1000/-home-nadeem-israr-Desktop-plan/74e0ed3f-508a-4e46-8044-4d5f5a386b98/scratchpad";
const b=await chromium.launch({headless:true,args:["--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader","--ignore-gpu-blocklist","--no-sandbox"]});
const p=await b.newPage({viewport:{width:1400,height:900}});
const errs=[];p.on("pageerror",e=>errs.push("PAGE:"+e.message));p.on("console",m=>{if(m.type()==="error"&&!m.text().includes("501"))errs.push("CON:"+m.text());});
await p.goto("http://localhost:3000/",{waitUntil:"networkidle"});
await p.waitForSelector("text=Turn a floor plan",{timeout:30000});
await p.click('button:has-text("Real parsed plan")');
await p.waitForTimeout(6500);
const box = await p.$eval("canvas", el=>{const r=el.getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height};});
await p.mouse.move(box.x+box.w/2, box.y+box.h/2);
for(let i=0;i<7;i++){await p.mouse.wheel(0,-200);await p.waitForTimeout(100);}
// drag to look toward indoor seating
await p.mouse.move(box.x+box.w/2, box.y+box.h*0.5); await p.mouse.down(); await p.mouse.move(box.x+box.w/2+120, box.y+box.h*0.5-30,{steps:15}); await p.mouse.up();
await p.waitForTimeout(1500);
await p.screenshot({path:SC+"/p8_models.png"});
console.log("ERR",errs.length); errs.slice(0,10).forEach(e=>console.log(e));
await b.close();
