import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const html=readFileSync(new URL('../public/index.html',import.meta.url),'utf8');
const start=html.indexOf('let navigationRequest=0;');
const end=html.indexOf("$('#gq').addEventListener",start);
assert.ok(start>=0 && end>start);
const code=html.slice(start,end);
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};};
function element(){return{innerHTML:'',children:[],setAttribute(){},appendChild(node){this.children.push(node);return node;},replaceChildren(node){this.children=[node];}};}
function text(node){return node.innerHTML+node.children.map(text).join('');}

for(const [mode,sub,view] of [['doctrine',null,'viewDoctrine'],['maint',null,'viewMaint'],
  ['corpus','corpus','viewCorpus'],['corpus','cases','viewCases'],['corpus','topics','viewTopics'],['corpus','graph','viewGraph']]) {
  for(const failure of [false,true]) test(`late ${mode}/${sub||'main'} ${failure?'error':'content'} cannot alter the new page`,async()=>{
    const host=element(),waiting=deferred(),started=deferred();let contextUpdates=0;
    const scope={state:{mode,sub},document:{createElement:element},$:()=>host,el:element,
      SUBS:[['corpus','文章'],['cases','判例'],['topics','标签'],['graph','图谱']],
      renderModes(){},renderContext(){contextUpdates++;},esc:String,
      viewApi:async node=>{node.innerHTML='CURRENT PAGE';},
      [view]:async node=>{started.resolve();await waiting.promise;node.innerHTML='STALE CONTENT';}};
    const context=vm.createContext(scope);vm.runInContext(code,context);
    const old=vm.runInContext('route()',context);await started.promise;
    scope.state.mode='api';await vm.runInContext('route()',context);
    assert.equal(text(host),'CURRENT PAGE');const count=contextUpdates;
    if(failure) waiting.reject(new Error('OLD ERROR'));else waiting.resolve();
    await old;assert.equal(text(host),'CURRENT PAGE');assert.equal(contextUpdates,count);
  });
}

test('a failure in the current page is still visible and escaped',async()=>{
  const host=element();const context=vm.createContext({state:{mode:'doctrine'},document:{createElement:element},$:()=>host,
    renderModes(){},renderContext(){},esc:s=>String(s).replace(/</g,'&lt;'),
    viewDoctrine:async()=>{throw Error('<broken>');}});
  vm.runInContext(code,context);await vm.runInContext('route()',context);
  assert.match(text(host),/加载失败/);assert.match(text(host),/&lt;broken>/);
});
