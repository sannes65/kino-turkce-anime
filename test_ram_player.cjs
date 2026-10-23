const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const assert = require('node:assert/strict');
function setup(handler) {
  const els = new Map();
  const element = id => {
    if (!els.has(id)) els.set(id,{hidden:true,innerHTML:'',textContent:'',querySelector:()=>element(id+' small')});
    return els.get(id);
  };
  const context = vm.createContext({setInterval,clearInterval,console,Number,Set,
    $:element,document:{contains:()=>true},icon:()=>'',esc:String,api:handler});
  vm.runInContext(fs.readFileSync(__dirname+'/public/ram-player.js','utf8')+'\nthis.Ram = KinoRamPlayer;',context);
  return new context.Ram('anime',1,true);
}
const entry = {id:'cache',state:'ready',playlist:'/ram/cache/playlist-0.m3u8',percent:100,bytes:100,height:720};
test('prepared playback resolves to local RAM source, not streaming fallback',async()=>{
  const r=setup(async path=>path.includes('prepare')?{entry}:{entry,entries:[entry],usedBytes:100,limitBytes:1024});
  try { assert.equal(await r.prepare(),entry.playlist); } finally { r.stop(); }
});
test('next episode starts at seven minutes and only once',async()=>{
  let calls=0;
  const r=setup(async(path,data)=>{
    if(data?.prefetch) {calls++; return {entry:{id:'next',state:'downloading'}};}
    return {entry,entries:[entry]};
  });
  r.entry=entry;
  await r.tick({duration:1440,currentTime:1019,ended:false}); assert.equal(calls,0);
  await Promise.all([r.tick({duration:1440,currentTime:1020,ended:false}),r.tick({duration:1440,currentTime:1021,ended:false})]);
  assert.equal(calls,1); r.stop();
});
test('disabled RAM and unknown duration never prefetch',async()=>{
  let calls=0; const r=setup(async()=>{calls++; return {entry};}); r.entry=entry;
  await r.tick({duration:NaN,currentTime:0});
  r.enabled=false; await r.tick({duration:100,currentTime:50});
  assert.equal(calls,0); assert.equal(await r.prepare(),null); r.stop();
});
test('stream action settles a pending preparation and clears timers',async()=>{
  const pending={id:'cache',state:'downloading',done:1,total:10,percent:10};
  const r=setup(async()=>({entry:pending,entries:[pending]}));
  const preparation=r.prepare(); await new Promise(setImmediate); await r.useStream();
  assert.equal(await preparation,null); assert.equal(r.timers.size,0); assert.equal(r.enabled,false); r.stop();
});
test('leaving the player settles a pending preparation',async()=>{
  const r=setup(async()=>({entry:{id:'cache',state:'resolving'}}));
  const preparation=r.prepare(); await new Promise(setImmediate); r.stop();
  assert.equal(await preparation,null); assert.equal(r.timers.size,0);
});
