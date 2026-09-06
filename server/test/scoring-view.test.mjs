import {test} from 'node:test';
import assert from 'node:assert/strict';
import {renderScoreResult,createScoreUpdater} from '../public/scoring-results.js';

const stage = changes => ({stage:'S',zh:'测试阶段',test_type:'balancing',weights:'assigned',
  score_low:-.3,score_high:.7,evidence_resolved:0,interval_decides:false,
  factors_present:[],factors_against:[],factors_absent:[],unresolved:[],next_evidence:[],...changes});
const result = changes => ({overall:'undetermined',stages:[stage(changes)]});

test('all-unknown scenario shows insufficient evidence and no conclusive badge',()=>{
  const html=renderScoreResult(result({interval_decides:true}));
  assert.match(html,/证据不足，无法判断/);
  assert.match(html,/已确认事实 0%/);
  assert.match(html,/不是胜诉概率|不表示胜诉概率/);
  assert.doesNotMatch(html,/tag ok|区间可定论|分档稳定/);
});

test('negative factors and unresolved evidence retain direction and nonnumeric gaps',()=>{
  const html=renderScoreResult(result({
    factors_against:[{id:'c',zh:'反向事实'}],
    next_evidence:[{zh:'未知反向事实',direction:'counter',maximum_swing:.3,look_for:'原件'},
      {zh:'缺少权重',direction:'pro'}],
  }));
  assert.match(html,/反向事实/);assert.match(html,/反向因素 · 最大影响 0.3 · 找：原件/);
  assert.match(html,/缺少权重/);assert.doesNotMatch(html,/NaN|undefined|Infinity/);
});

test('a point interval is not displayed as an invented minimum-width interval',()=>{
  const html=renderScoreResult(result({score_low:0,score_high:0,evidence_resolved:1}));
  assert.match(html,/width:0.00%/);
});

test('missing and malformed numeric intervals never enter arithmetic rendering',()=>{
  for(const fields of [{score_low:null},{score_high:NaN},{score_low:Infinity},
    {score_low:.4,score_high:-.1},{weights:'incomplete'},{weights:'unassigned'}]){
    const html=renderScoreResult(result(fields));
    assert.doesNotMatch(html,/rngspan|NaN|Infinity|undefined/);
    assert.match(html,/暂不计算|未赋值/);
  }
});

test('all nonbalancing branches remain manual or checklist states without numbers',()=>{
  for(const test_type of ['conjunctive','disjunctive-gateway','presumption-rebuttal','threshold-discretion','future-type']){
    const html=renderScoreResult(result({test_type,result:'manual-checklist',score_low:.8,score_high:.9}));
    assert.match(html,/需要人工判断/);
    assert.doesNotMatch(html,/rngspan|启发式情景区间|权重|校准|已开门槛/);
  }
});

test('numeric bars stay within their container even outside the original unit range',()=>{
  const html=renderScoreResult(result({score_low:-3,score_high:2,evidence_resolved:1}));
  const [,left,width]=html.match(/class="rngspan" style="left:([\d.]+)%;width:([\d.]+)%/);
  assert.ok(+left>=0 && +width>=0 && +left + +width<=100);
});

test('result text from API is escaped',()=>{
  const attack='<img src=x onerror="alert(1)">';
  const html=renderScoreResult({overall_reason:attack,stages:[stage({zh:attack,reason:attack,
    unresolved:[{zh:attack}],next_evidence:[{zh:attack,look_for:attack}]})]});
  assert.doesNotMatch(html,/<img|onerror="/);
  assert.match(html,/&lt;img/);
});

function harness(){
  const requests=[],events=[];
  let visible=true;
  const update=createScoreUpdater({
    fetchScore:(facts,signal)=>new Promise((resolve,reject)=>requests.push({facts,signal,resolve,reject})),
    isCurrent:()=>visible,
    onLoading:()=>events.push(['loading']),onResult:html=>events.push(['result',html]),
    onError:message=>events.push(['error',message]),
  });
  return {requests,events,update,leave:()=>{visible=false;}};
}

test('a later choice wins even when the server ignores cancellation',async()=>{
  const h=harness(),facts={f:true};
  const first=h.update(facts);facts.f=false;
  const second=h.update(facts);
  assert.deepEqual(h.requests[0].facts,{f:true});
  assert.equal(h.requests[0].signal.aborted,true);
  h.requests[1].resolve(result({zh:'最新选择'}));await second;
  h.requests[0].resolve(result({zh:'旧选择'}));await first;
  const outputs=h.events.filter(e=>e[0]==='result');
  assert.equal(outputs.length,1);assert.match(outputs[0][1],/最新选择/);
});

test('late errors cannot overwrite a newer result',async()=>{
  const h=harness(),first=h.update({}),second=h.update({f:false});
  h.requests[1].resolve(result());await second;
  h.requests[0].reject(new Error('old failure'));await first;
  assert.equal(h.events.filter(e=>e[0]==='error').length,0);
});

test('navigation prevents a pending response from painting into another view',async()=>{
  const h=harness(),pending=h.update({});h.leave();
  h.requests[0].resolve(result());await pending;
  assert.deepEqual(h.events,[['loading']]);
});

test('current errors are visible and a subsequent retry can succeed',async()=>{
  const h=harness(),failed=h.update({});h.requests[0].reject(new Error('offline'));await failed;
  assert.deepEqual(h.events.at(-1),['error','offline']);
  const retry=h.update({});h.requests[1].resolve(result());await retry;
  assert.equal(h.events.at(-1)[0],'result');
});

test('invalid server response is an error instead of stale or empty results',async()=>{
  const h=harness(),pending=h.update({});h.requests[0].resolve({error:'bad request'});await pending;
  assert.equal(h.events.at(-1)[0],'error');
  assert.throws(()=>renderScoreResult({stages:[]}),/没有返回有效阶段/);
});
