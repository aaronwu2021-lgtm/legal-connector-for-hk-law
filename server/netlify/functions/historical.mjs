// Historical views contain dated identity/evidence metadata only. The current
// library has no versioned rule text; a decision year does not date its notes.
const own = (o,k) => Object.prototype.hasOwnProperty.call(o,k);
const select = (o,keys) => Object.fromEntries(keys.filter(k=>o[k]!==undefined).map(k=>[k,o[k]]));
const RULE_GAP = 'historical-rule-not-modelled';
const DATE_ERROR = {error:'as_of must be a year from 1000 to 9999 or a valid YYYY-MM-DD date.',code:'invalid-as-of'};

export function parseAsOf(value) {
  if (value === undefined) return null;
  if (typeof value === 'number') {
    if (!Number.isInteger(value) || value < 1000 || value > 9999) return {...DATE_ERROR};
    return {as_of:value,year:value,date:String(value)+'-12-31',precision:'year'};
  }
  if (typeof value !== 'string') return {...DATE_ERROR};
  if (/^[1-9]\d{3}$/.test(value)) return parseAsOf(Number(value));
  if (!/^[1-9]\d{3}-\d{2}-\d{2}$/.test(value)) return {...DATE_ERROR};
  const [year,month,day]=value.split('-').map(Number);
  const date=new Date(Date.UTC(year,month-1,day));
  if(date.getUTCFullYear()!==year || date.getUTCMonth()!==month-1 || date.getUTCDate()!==day) return {...DATE_ERROR};
  return {as_of:value,year,date:value,precision:'day'};
}

function chronology(record) {
  const citation=String(record.cite || record.citation || '');
  const neutrals=[...citation.matchAll(/\[(\d{4})\]\s*(?:UKSC|UKHL|EWCA\s+(?:Civ|Crim)|EWHC|HKCFA|HKCA|HKCFI|HKDC|SGCA|SGHC|HCA|FCAFC|FCA)\s+\d+/gi)];
  const years=[record.year,record.y].filter(value=>value!==undefined && value!==null);
  if(years.some(value=>typeof value!=='number' || !Number.isInteger(value) || value<1000 || value>9999)) return {reason:'invalid-record-date'};
  years.push(...neutrals.map(match=>Number(match[1])));
  if(new Set(years).size>1) return {reason:'conflicting-record-date'};
  if (record.decision_date !== undefined) {
    const parsed=parseAsOf(record.decision_date);
    if (!parsed || parsed.error || parsed.precision!=='day') return {reason:'invalid-record-date'};
    if (years.some(year=>year!==parsed.year)) return {reason:'conflicting-record-date'};
    return {...parsed,date_precision:'decision-date'};
  }
  const cited=neutrals[0] || citation.match(/[\[(](\d{4})[\])]/);
  const year=record.year ?? record.y ?? (cited ? Number(cited[1]) : undefined);
  const parsed=parseAsOf(year);
  if (!parsed || parsed.error || parsed.precision!=='year') return {reason:'undated-record'};
  return {...parsed,date_precision:record.year!==undefined || record.y!==undefined ? 'year' : 'citation-year'};
}

export function eligibleAt(record,cutoff) {
  const dated=chronology(record);
  if (dated.reason) return {eligible:false,reason:dated.reason};
  if (dated.year>cutoff.year || (dated.precision==='day' && dated.date>cutoff.date)) return {eligible:false,reason:'after-cutoff'};
  if (dated.precision==='year' && dated.year===cutoff.year && cutoff.date < String(cutoff.year)+'-12-31') {
    return {eligible:false,reason:'insufficient-date-precision'};
  }
  return {eligible:true,year:dated.year,date_precision:dated.date_precision,
    ...(dated.precision==='day' ? {decision_date:dated.date} : {})};
}

function identity(record) {
  return {...select(record,['cite','court','year','decision_date','court_rank','where','jurisdiction']),
    case:record.case || record.name, ...(record.citation && !record.cite ? {cite:record.citation} : {})};
}

function evidenceChronologyKnown(record) {
  // Free-text sources and quoted passages lack a structured source chronology.
  // Keep these records out of historical evidence instead of stripping their
  // source while retaining a quoted/primary verification label.
  return !['verified-quoted','quoted'].includes(record.verified) && !own(record,'source') && !own(record,'src');
}

export function createHistoricalLibrary(elements,moduleTimelines={}) {
  function context(cutoff) {
    const excluded={};
    const count=reason=>{excluded[reason]=(excluded[reason]||0)+1;};
    const meta=()=>({as_of:cutoff.as_of,historical_mode:'strict',historical_rule_status:RULE_GAP,
      historical_limitations:{excluded_counts:{...excluded},
        rule_text:'Current tests, statutes, holdings, effects and editorial notes are not versioned and are withheld.',
        dates:'Year-only records are eligible at year-end; earlier dates in the same year require a full decision date.',
        verification:'Verification labels describe the current catalogue record, not what had been verified at the cutoff.'}});
    function authority(record,where) {
      const eligibility=eligibleAt(record,cutoff);
      if (!eligibility.eligible) {count(eligibility.reason);return null;}
      const citationYears=[...String(record.cite||record.citation||'').matchAll(/[\[(](\d{4})[\])]/g)].map(m=>Number(m[1]));
      if(citationYears.some(year=>year>cutoff.year)) {count('citation-after-cutoff');return null;}
      if (!evidenceChronologyKnown(record)) {count('source-chronology-not-modelled');return null;}
      return {...identity(record),year:eligibility.year,date_precision:eligibility.date_precision,
        ...(eligibility.decision_date ? {decision_date:eligibility.decision_date} : {}),
        ...select(record,['pin','verified']),where:record.where || where,
        proposition_check:'not-performed',historical_rule_status:RULE_GAP};
    }
    const authorities=(records,where)=>(records||[]).map((r,i)=>authority(r,where+'['+i+']')).filter(Boolean);
    function node(record,where) {
      const out={...select(record,['id','zh','en','drift','variant']),historical_rule_status:RULE_GAP};
      if (record.auth) out.auth=authorities(record.auth,where+'.auth');
      if (record.sub_tests) out.sub_tests=record.sub_tests.map((r,i)=>node(r,where+'.sub_tests['+i+']'));
      return out;
    }
    function jurisdiction(j) {
      const raw=own(elements.jurisdictions,j)?elements.jurisdictions[j]:null;
      if(!raw) return undefined;
      return {id:j,...select(raw,['name']),historical_rule_status:RULE_GAP,
        cases:authorities(raw.cases,'jurisdictions.'+j+'.cases')};
    }
    return {count,meta,authority,authorities,node,jurisdiction};
  }

  function timeline(id,cutoff,jFilter) {
    if(jFilter!==undefined && (!Array.isArray(jFilter) || jFilter.some(j=>typeof j!=='string' || !j.trim()))) {
      return {error:'jurisdictions must be an array of non-empty strings.',code:'invalid-jurisdictions'};
    }
    const raw=own(elements.timelines,id)?elements.timelines[id]:own(moduleTimelines,id)?moduleTimelines[id]:null;
    if(!raw || !Array.isArray(raw.events)) return {error:'unknown timeline'};
    const ctx=context(cutoff),all=raw.events.filter(e=>!jFilter || jFilter.includes(e.j));
    const events=[];
    for(const event of all) {
      const eligible=eligibleAt(event,cutoff);
      if(!eligible.eligible){ctx.count(eligible.reason);continue;}
      events.push({...select(event,['j','case','court','court_rank']),y:eligible.year,
        ...(eligible.decision_date ? {decision_date:eligible.decision_date} : {}),
        date_precision:eligible.date_precision,in_force_at_as_of:true,historical_rule_status:RULE_GAP});
    }
    events.sort((a,b)=>a.y-b.y || String(a.decision_date||'').localeCompare(String(b.decision_date||'')));
    // Year-only dates overlap every precise date in that year. Preserve all
    // possible most recent records rather than breaking ties by array order.
    const recent=records=>{
      const year=Math.max(...records.map(e=>e.y));
      const sameYear=records.filter(e=>e.y===year);
      const lastDate=sameYear.map(e=>e.decision_date||'').sort().at(-1);
      return sameYear.filter(e=>!e.decision_date || e.decision_date===lastDate);
    };
    const standing={},latest={};
    for(const j of new Set(events.map(e=>e.j))){
      const local=events.filter(e=>e.j===j),rank=Math.max(...local.map(e=>e.court_rank??2));
      latest[j]=recent(local);
      standing[j]=recent(local.filter(e=>(e.court_rank??2)===rank));
    }
    const row=e=>({jurisdiction:e.j,since:e.y,case:e.case,court:e.court,court_rank:e.court_rank,
      ...(e.decision_date ? {decision_date:e.decision_date} : {}),
      date_precision:e.date_precision,historical_rule_status:RULE_GAP});
    const differences={};
    for(const [j,candidates]of Object.entries(latest)) if(candidates.length===1 && standing[j].length===1 && candidates[0]!==standing[j][0]) differences[j]={latest_event:{year:candidates[0].y,...row(candidates[0])},governing:{year:standing[j][0].y,...row(standing[j][0])},
      note:'Rank and recency identify different recorded authorities; historical rule text is not modelled.'};
    const rows=groups=>Object.values(groups).flatMap(candidates=>candidates.map(e=>({...row(e),
      recency_status:candidates.length>1?'recency-unresolved':'unique-dated-candidate'})));
    return {id,...select(raw,['title','title_en','sub_test']),...ctx.meta(),events,
      standing_rules:rows(standing),latest_rules:rows(latest),
      recency_unresolved_jurisdictions:Object.keys(latest).filter(j=>latest[j].length>1 || standing[j].length>1),
      latest_is_not_governing:Object.keys(differences).length?differences:undefined,
      subordinate_conflicts_status:RULE_GAP,
      jurisdictions_with_no_authority_at_as_of:[...new Set(all.map(e=>e.j))].filter(j=>!standing[j]),
      resolution:'Rank then supported recency selects recorded authority metadata; overlapping dates remain tied. This does not establish a binding historical legal rule.'};
  }

  function allElements(cutoff,j) {
    const ctx=context(cutoff);
    const out={claim:elements.claim,version:elements.version,variants:elements.variants,
      elements:elements.elements.map((r,i)=>ctx.node(r,'elements['+i+']')),
      defences:elements.defences.map((r,i)=>ctx.node(r,'defences['+i+']'))};
    if(j) out.jurisdiction=ctx.jurisdiction(j);
    else out.jurisdictions=Object.fromEntries(Object.keys(elements.jurisdictions).map(k=>[k,ctx.jurisdiction(k)]));
    return {...out,...ctx.meta()};
  }

  function element(id,cutoff) {
    const ctx=context(cutoff);
    for(const [i,raw] of elements.elements.entries()) {
      if(raw.id===id) return {kind:'element',element:ctx.node(raw,'elements['+i+']'),...ctx.meta()};
      for(const [k,sub]of raw.sub_tests.entries()) if(sub.id===id) return {kind:'sub_test',
        element:ctx.node(raw,'elements['+i+']'),sub_test:ctx.node(sub,'elements['+i+'].sub_tests['+k+']'),
        timeline:sub.drift?timeline(sub.drift,cutoff):null,...ctx.meta()};
    }
    for(const [i,raw]of elements.defences.entries()) if(raw.id===id) return {kind:'defence',defence:ctx.node(raw,'defences['+i+']'),
      timeline:raw.drift?timeline(raw.drift,cutoff):null,...ctx.meta()};
    return {error:'unknown element'};
  }

  function checklist(j,variant,cutoff) {
    const ctx=context(cutoff),rows=[];
    const local=own(elements.jurisdictions,j)?elements.jurisdictions[j].cases||[]:[];
    for(const el of elements.elements) for(const st of el.sub_tests) {
      if(st.variant && variant && st.variant!==variant) continue;
      const drift=st.drift ? timeline(st.drift,cutoff,j?[j]:undefined) : null;
      rows.push({element:el.id,element_en:el.en,sub_test:st.id,sub_test_en:st.en,historical_rule_status:RULE_GAP,
        backbone_authority:ctx.authorities(st.auth,st.id+'.auth'),
        local_authority:ctx.authorities(local.filter(c=>(c.maps_to||[]).includes(st.id)),j+'.'+st.id),
        related_local_authority:ctx.authorities(local.filter(c=>!(c.maps_to||[]).includes(st.id)&&(c.maps_to||[]).includes(el.id)),j+'.'+el.id),
        standing_rule_as_of:drift?.standing_rules.find(r=>(!j || r.jurisdiction===j)&&r.recency_status!=='recency-unresolved'),
        standing_authorities_as_of:drift?.standing_rules.filter(r=>!j || r.jurisdiction===j),
        historical_rule_gap:RULE_GAP});
    }
    const defences=elements.defences.map(d=>({id:d.id,en:d.en,historical_rule_status:RULE_GAP,
      authority:ctx.authorities(d.auth,d.id+'.auth')}));
    return {claim:elements.claim,jurisdiction:own(elements.jurisdictions,j)?j:null,variant:variant||'any',
      elements:rows,defences_to_anticipate:defences,...ctx.meta()};
  }

  function verification(current,cutoff) {
    const ctx=context(cutoff);
    if(!current.found || !current.authority) return {
      ...select(current,['found','status','matched_by','citation','error','code','proposition_check']),
      ...ctx.meta(),proposition_check:'not-performed'};
    const authority=current.authority;
    const usable=eligibleAt(authority,cutoff);
    const identityOnly={...identity(authority),identity_only:true};
    const result={found:true,identity_exists:true,usable_at_as_of:usable.eligible,
      ...select(current,['matched_by','persuasive_only','hk_status']),authority:identityOnly,
      proposition_check:'not-performed',evidence_records:[]};
    if(!usable.eligible) ctx.count(usable.reason);
    else {
      const records=current.evidence_records || current.records || [authority];
      result.evidence_records=ctx.authorities(records,'verification.evidence');
      result.evidence_available_at_as_of=result.evidence_records.length>0;
    }
    return {...result,...ctx.meta()};
  }
  return {timeline,elements:allElements,element,checklist,verification};
}
