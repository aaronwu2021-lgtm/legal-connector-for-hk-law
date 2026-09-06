// A successful metadata response establishes retrieval at one neutral citation,
// never that a party name, quoted passage or legal proposition was verified.
const LIMIT=4*1024*1024;
const neutralPattern=/\[([1-9]\d{3})\]\s*HK(CFA|CA|CFI|DC)\s*([1-9]\d*)\b/gi;
const normalize=s=>s.replace(/\s+/g,'').toUpperCase();
const result=(status,extra={})=>({status,exists:null,proposition_check:'not-performed',...extra});
const discard=async response=>{try{await response.body?.cancel();}catch{}};

async function readJson(response) {
  const type=response.headers.get('content-type')||'';
  if(!/^application\/(?:[\w.-]+\+)?json\b/i.test(type)) {await discard(response);throw new Error('invalid-content-type');}
  if(Number(response.headers.get('content-length'))>LIMIT) {await discard(response);throw new Error('response-too-large');}
  const reader=response.body?.getReader();
  if(!reader) throw new Error('missing-response-body');
  const chunks=[]; let size=0;
  try {
    while(true){
      const {done,value}=await reader.read(); if(done) break;
      size+=value.byteLength;
      if(size>LIMIT) throw new Error('response-too-large');
      chunks.push(value);
    }
  } catch(error) { await reader.cancel().catch(()=>{}); throw error; }
  finally { reader.releaseLock(); }
  const bytes=new Uint8Array(size); let offset=0;
  for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
  return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
}

export async function liveCitation(citation,local,{historical=false,disabled=false,fetcher=globalThis.fetch}={}) {
  if(disabled) return undefined;
  const matches=[...citation.matchAll(neutralPattern)];
  if(!matches.length) return undefined;
  if(historical) return result('not-requested-historical',{
    note:'Current online material is not added to a historical projection.'});
  const distinct=new Set(matches.map(m=>normalize(m[0])));
  if(distinct.size!==1 || local.citation_mismatch || ['citation-mismatch','ambiguous'].includes(local.status)) {
    return result('not-requested-identity-conflict');
  }
  const match=matches[0];
  // An unlisted citation by itself can still be retrieved. An unresolved name
  // or extra citation needs identity review before a live result is associated.
  if(!local.found && normalize(citation.trim())!==normalize(match[0])) {
    return result('not-requested-identity-unresolved');
  }
  const neutral=`[${match[1]}] HK${match[2].toUpperCase()} ${match[3]}`;
  const url=`https://www.hklii.hk/api/getjudgment?lang=en&abbr=hk${match[2].toLowerCase()}&year=${match[1]}&num=${match[3]}`;
  let response;
  try {
    response=await fetcher(url,{headers:{accept:'application/json'},signal:AbortSignal.timeout(10000),redirect:'error'});
    if(response.redirected) {await discard(response);return result('unexpected-redirect');}
    if(!response.ok) {
      await discard(response);
      if(response.status===404) return result('english-version-unavailable',{
        http_status:404,english_judgment_available:false,
        note:'This English endpoint did not supply a judgment; case existence and other language versions remain unresolved.'});
      return result('upstream-unavailable',{http_status:response.status,
        note:'Retrieval failed; this does not establish that the citation is absent.'});
    }
    const document=await readJson(response);
    if(!document || typeof document!=='object' || Array.isArray(document)
      || typeof document.neutral!=='string' || typeof document.content!=='string' || !document.content.trim()
      || typeof document.db!=='string' || !document.db.trim() || typeof document.date!=='string') {
      return result('invalid-response');
    }
    if(normalize(document.neutral)!==normalize(neutral)) return result('response-citation-mismatch');
    const date=document.date.slice(0,10);
    if(!/^[1-9]\d{3}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))?$/.test(document.date)
      || Number.isNaN(Date.parse(document.date)) || Number.isNaN(Date.parse(date))
      || new Date(date).toISOString().slice(0,10)!==date || date.slice(0,4)!==match[1]) {
      return result('invalid-response');
    }
    return result('matched-neutral',{
      exists:true,neutral,court:document.db,date,english_judgment_available:true,
      title:document.content.match(/<title\b[^>]*>([^<]{1,160})<\/title>/i)?.[1],
      identity_scope:'neutral-citation-only',source_url:url,
      note:'The returned neutral citation matches. Party names, pin cites and legal propositions were not checked; catalogue verification levels are unchanged.'});
  } catch(error) {
    return result(error?.name==='TimeoutError' || error?.name==='AbortError' ? 'upstream-timeout'
      : response?.ok ? 'invalid-response' : 'upstream-unavailable');
  }
}
