import {test,after} from 'node:test';
import assert from 'node:assert/strict';
import {liveCitation} from '../netlify/functions/live-citation.mjs';
import handler from '../netlify/functions/api.mjs';

const citation='[2022] HKCFA 25';
const fixture={neutral:citation,date:'2022-12-12T00:00:00+08:00',db:'Court of Final Appeal',
  content:'<html><head><title>Fixture judgment</title></head><body>Fixture text</body></html>'};
const make=value=>new Response(JSON.stringify(value),{headers:{'content-type':'application/json'}});
const missing={found:false,status:'unresolved-citation',citation_mismatch:false};
const matched={found:true,status:'matched'};
const originalFetch=globalThis.fetch;
after(()=>{globalThis.fetch=originalFetch;});
globalThis.fetch=async()=>{throw Error('Unexpected real network call');};

test('a matching response identifies only the retrieved neutral citation',async()=>{
  let calls=0;
  const local={...matched,authority:{verified:'unverified',pin:'original'}};
  const before=JSON.stringify(local);
  const result=await liveCitation(citation,local,{fetcher:async(url,options)=>{
    calls++;assert.equal(new URL(url).hostname,'www.hklii.hk');
    assert.equal(new URL(url).searchParams.get('abbr'),'hkcfa');
    assert.equal(options.redirect,'error');assert.ok(options.signal);
    return make(fixture);
  }});
  assert.equal(calls,1);assert.equal(result.exists,true);
  assert.equal(result.identity_scope,'neutral-citation-only');
  assert.equal(result.proposition_check,'not-performed');
  assert.equal(result.verified,undefined);assert.equal(result.pin,undefined);
  assert.equal(result.title,'Fixture judgment');assert.equal(JSON.stringify(local),before);
});

test('an unlisted bare neutral can be retrieved without making it a catalogue match',async()=>{
  const result=await liveCitation(citation,missing,{fetcher:async()=>make(fixture)});
  assert.equal(result.exists,true);assert.equal(missing.found,false);
});

test('historical, disabled, conflicting, multiple and unresolved named queries do not request live content',async()=>{
  const denied=async()=>assert.fail('must not fetch');
  for(const [query,local,options,status] of [
    [citation,matched,{historical:true},'not-requested-historical'],
    [citation,matched,{disabled:true},undefined],
    [citation,{...matched,citation_mismatch:true},{},'not-requested-identity-conflict'],
    [citation,{status:'ambiguous'},{},'not-requested-identity-conflict'],
    [citation+'; [2023] HKCFA 16',matched,{},'not-requested-identity-conflict'],
    ['Unrecorded v Parties '+citation,missing,{},'not-requested-identity-unresolved'],
    [citation+'; [2099] UKSC 9',missing,{},'not-requested-identity-unresolved'],
    ['[2022] UKSC 25',matched,{},undefined],
  ]) assert.equal((await liveCitation(query,local,{...options,fetcher:denied}))?.status,status);
});

for(const status of [403,404,429,500,503]) test(`HTTP ${status} does not establish that a case is absent`,async()=>{
  const result=await liveCitation(citation,matched,{fetcher:async()=>new Response('',{status})});
  assert.equal(result.exists,null);assert.equal(result.http_status,status);
  assert.equal(result.status,status===404?'english-version-unavailable':'upstream-unavailable');
});

test('malformed and mismatched HTTP 200 responses cannot verify a citation',async()=>{
  for(const value of [null,[],{}, {error:'not found'}, {...fixture,neutral:'[2023] HKCFA 16'},
    {...fixture,content:''},{...fixture,content:{}},{...fixture,db:null},{...fixture,date:2022},
    {...fixture,date:'2022-02-30'},{...fixture,date:'2023-12-12'}, {...fixture,neutral:25}]) {
    const result=await liveCitation(citation,matched,{fetcher:async()=>make(value)});
    assert.equal(result.exists,null,JSON.stringify(value));
    assert.ok(['invalid-response','response-citation-mismatch'].includes(result.status));
  }
  for(const response of [new Response('<html>Error</html>',{headers:{'content-type':'text/html'}}),
    new Response('{bad json',{headers:{'content-type':'application/json'}}),
    new Response('{}',{headers:{'content-type':'application/json','content-length':'9999999'}})]) {
    assert.equal((await liveCitation(citation,matched,{fetcher:async()=>response})).status,'invalid-response');
  }
});

test('transport errors and timeouts remain unknown and do not expose raw errors',async()=>{
  for(const [error,status] of [[new Error('secret request URL'),'upstream-unavailable'],
    [new DOMException('expired','TimeoutError'),'upstream-timeout'],[new DOMException('aborted','AbortError'),'upstream-timeout']]) {
    const result=await liveCitation(citation,matched,{fetcher:async()=>{throw error;}});
    assert.equal(result.status,status);assert.equal(result.exists,null);
    assert.ok(!JSON.stringify(result).includes(error.message));
  }
});

test('public historical REST results never reintroduce online title, date or source',async()=>{
  let calls=0;globalThis.fetch=async()=>{calls++;return make(fixture);};
  try {
    const response=await handler(new Request('http://offline.invalid/api/verify?cite='+encodeURIComponent(citation)+'&as_of=1990'));
    const result=await response.json();
    assert.equal(response.status,200);assert.equal(calls,0);
    assert.equal(result.hklii.status,'not-requested-historical');
    assert.equal(result.hklii.exists,null);
    assert.doesNotMatch(JSON.stringify(result.hklii),/Fixture|2022-12-12/);
  } finally {globalThis.fetch=async()=>{throw Error('Unexpected network');};}
});

test('public REST retains catalogue mismatch when live data would otherwise succeed',async()=>{
  let calls=0;globalThis.fetch=async()=>{calls++;return make(fixture);};
  try {
    const query='Hayward v Zurich '+citation;
    const response=await handler(new Request('http://offline.invalid/api/verify?cite='+encodeURIComponent(query)));
    const result=await response.json();
    assert.equal(calls,0);assert.equal(result.found,false);
    assert.equal(result.hklii.exists,null);
  } finally {globalThis.fetch=async()=>{throw Error('Unexpected network');};}
});
