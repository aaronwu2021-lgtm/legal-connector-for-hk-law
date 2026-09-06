import {test} from 'node:test';
import assert from 'node:assert/strict';
import ELEMENTS from '../netlify/functions/_elements.mjs';
import {parseAsOf,eligibleAt,createHistoricalLibrary} from '../netlify/functions/historical.mjs';

const library=createHistoricalLibrary(ELEMENTS);
const cutoff=value=>{const parsed=parseAsOf(value);assert.ok(parsed&&!parsed.error);return parsed;};

test('one strict cutoff parser accepts years and actual calendar dates',()=>{
  assert.equal(parseAsOf(undefined),null);
  assert.deepEqual(parseAsOf('1990'),parseAsOf(1990));
  assert.equal(parseAsOf(1990).date,'1990-12-31');
  for(const date of ['2000-02-29','2024-02-29','2026-09-05','1000-01-01','9999-12-31']) {
    assert.equal(parseAsOf(date).date,date);
  }
  for(const value of [null,true,false,0,999,10000,2026.5,NaN,Infinity,[],{},'',
    ' 1990','1990 ','1990.0','2026-2-01','2026-02-29','1900-02-29','2026-04-31',
    '2026-00-01','2026-13-01','2026-01-00','2026-01-32','2026-09-05T00:00:00Z']) {
    assert.equal(parseAsOf(value)?.code,'invalid-as-of',String(value));
  }
});

test('year precision cannot establish eligibility within the same year',()=>{
  assert.equal(eligibleAt({year:2024},cutoff('2024-01-01')).reason,'insufficient-date-precision');
  assert.equal(eligibleAt({year:2024},cutoff('2024-12-30')).eligible,false);
  assert.equal(eligibleAt({year:2024},cutoff('2024-12-31')).eligible,true);
  assert.equal(eligibleAt({year:2024},cutoff(2024)).eligible,true);
  assert.equal(eligibleAt({decision_date:'2024-02-29'},cutoff('2024-02-28')).eligible,false);
  assert.equal(eligibleAt({decision_date:'2024-02-29'},cutoff('2024-02-29')).eligible,true);
  assert.equal(eligibleAt({year:2023,decision_date:'2024-02-29'},cutoff(2025)).reason,'conflicting-record-date');
  assert.equal(eligibleAt({},cutoff(2026)).reason,'undated-record');
  assert.equal(eligibleAt({year:1990,cite:'[2026] UKSC 1'},cutoff(1990)).reason,'conflicting-record-date');
});

test('a 1990 checklist removes later authorities and all unversioned legal prose',()=>{
  const output=library.checklist('HK',null,cutoff(1990)),json=JSON.stringify(output);
  for(const text of ['Long Year','Joytex','Hayward','Koo Ming','Chang Pui','Alireza','Green Park','San-Hot','2016','2026']) {
    assert.ok(!json.includes(text),'leaked '+text);
  }
  assert.match(json,/historical-rule-not-modelled/);
  assert.ok(output.historical_limitations.excluded_counts['after-cutoff']>0);
  for(const row of output.elements) {
    assert.equal(row.plead,undefined);assert.equal(row.statute,undefined);
    for(const record of [...row.backbone_authority,...row.local_authority,...row.related_local_authority]) {
      assert.ok(record.year<=1990);assert.equal(record.holding,undefined);assert.equal(record.note,undefined);
    }
  }
});

test('retrospective prose does not survive a valid older event date',()=>{
  const output=library.timeline('T2',cutoff(2013),['SG']),json=JSON.stringify(output);
  assert.ok(output.events.some(e=>e.y===2013));
  assert.ok(!json.includes('2016'));assert.ok(!json.includes('England'));
  assert.ok(!json.includes('same position'));assert.equal(output.note,undefined);
  assert.ok(output.events.every(e=>e.eff===undefined&&e.treat===undefined&&e.f===undefined));
  assert.ok(output.standing_rules.every(e=>e.effect===undefined));
});

test('parent, sibling, defence and jurisdiction objects are all projected',()=>{
  for(const out of [library.element('E3c',cutoff(1990)),library.element('D1',cutoff(1990)),
    library.elements(cutoff(1990),'HK'),library.elements(cutoff(1990))]) {
    const json=JSON.stringify(out);
    for(const text of ['Hayward','Joytex','Shine Grace','Li Yuhong','2016','2026','statute_by_jurisdiction']) {
      assert.ok(!json.includes(text),'leaked '+text);
    }
  }
});

test('quoted evidence through later sources is withheld without relabelling it',()=>{
  const original=ELEMENTS.elements.find(e=>e.id==='E5').sub_tests.find(s=>s.id==='E5c').auth
    .find(a=>a.case.includes('Long Year'));
  const before=JSON.stringify(original);
  const out=library.verification({found:true,authority:original,evidence_records:[original]},cutoff(1991));
  assert.equal(out.identity_exists,true);assert.equal(out.usable_at_as_of,true);
  assert.equal(out.authority.identity_only,true);assert.equal(out.authority.verified,undefined);
  assert.deepEqual(out.evidence_records,[]);
  assert.equal(out.historical_limitations.excluded_counts['source-chronology-not-modelled'],1);
  assert.doesNotMatch(JSON.stringify(out),/Wong Yuk Lan|Joytex|2024|2026|verified-quoted/);
  assert.equal(JSON.stringify(original),before);
});

test('eligible primary evidence retains its original pin, level and location',()=>{
  const record={case:'Test v Fixture',cite:'[2000] UKHL 1',court:'HL',verified:'verified-primary',
    pin:'[4]',where:'original.location',note:'An editorial comparison with a later 2099 case'};
  const out=library.verification({found:true,authority:record,evidence_records:[record]},cutoff(2000));
  assert.equal(out.evidence_records[0].pin,'[4]');
  assert.equal(out.evidence_records[0].verified,'verified-primary');
  assert.equal(out.evidence_records[0].where,'original.location');
  assert.equal(out.proposition_check,'not-performed');
  assert.doesNotMatch(JSON.stringify(out),/2099|editorial comparison/);
});

test('direct future-case query returns identity metadata without future evidence',()=>{
  const record={case:'Future v Fixture',cite:'[2026] UKSC 1',year:2026,verified:'verified-primary',
    pin:'[8]',holding:'FUTURE HOLDING',source:'FUTURE SOURCE',note:'FUTURE COMMENT'};
  const out=library.verification({found:true,authority:record,evidence_records:[record]},cutoff(1990));
  assert.equal(out.identity_exists,true);assert.equal(out.usable_at_as_of,false);
  assert.equal(out.authority.case,record.case);assert.equal(out.authority.identity_only,true);
  assert.deepEqual(out.evidence_records,[]);
  assert.doesNotMatch(JSON.stringify(out),/FUTURE HOLDING|FUTURE SOURCE|FUTURE COMMENT|verified-primary/);
});

test('rank and recency stay distinct when historical rule text is unavailable',()=>{
  const out=library.timeline('T2',cutoff(2019),['EN']);
  assert.equal(out.standing_rules[0].since,2016);
  assert.equal(out.latest_rules[0].since,2019);
  assert.ok(out.latest_is_not_governing.EN);
  assert.equal(out.subordinate_conflicts_status,'historical-rule-not-modelled');
  assert.equal(out.standing_rules[0].effect,undefined);
});

test('future parallel report citations are not smuggled into an older evidence record',()=>{
  const out=library.verification({found:true,authority:{case:'Synthetic v Fixture',year:2016,cite:'[2016] UKSC 1; [2017] AC 1'},
    evidence_records:[{case:'Synthetic v Fixture',year:2016,cite:'[2016] UKSC 1; [2017] AC 1',verified:'verified-primary',pin:'[1]'}]},cutoff(2016));
  assert.equal(out.identity_exists,true); // direct identity metadata remains distinct
  assert.deepEqual(out.evidence_records,[]);
  assert.equal(out.historical_limitations.excluded_counts['citation-after-cutoff'],1);
});

test('all projections leave the current data and complete provenance intact',()=>{
  const before=JSON.stringify(ELEMENTS);
  for(const year of [1000,1990,2013,2026,9999]) {
    library.elements(cutoff(year));library.checklist('HK',null,cutoff(year));
    for(const id of Object.keys(ELEMENTS.timelines)) library.timeline(id,cutoff(year));
  }
  assert.equal(JSON.stringify(ELEMENTS),before);
});

test('precise cutoff retains decision dates in timeline authority summaries',()=>{
  const fixture=createHistoricalLibrary({...ELEMENTS,timelines:{dated:{events:[
    {j:'HK',y:2022,decision_date:'2022-12-12',case:'Dated apex',court_rank:4},
    {j:'HK',y:2022,decision_date:'2022-12-13',case:'Dated lower',court_rank:2},
    {j:'HK',y:2022,decision_date:'2022-12-15',case:'Future',court_rank:4},
    {j:'HK',y:2022,case:'Year only',court_rank:4}
  ]}}});
  const out=fixture.timeline('dated',cutoff('2022-12-14'));
  assert.equal(out.events.length,2);
  assert.equal(out.standing_rules[0].decision_date,'2022-12-12');
  assert.equal(out.latest_rules[0].decision_date,'2022-12-13');
  assert.equal(out.latest_is_not_governing.HK.governing.decision_date,'2022-12-12');
  assert.equal(out.latest_is_not_governing.HK.latest_event.decision_date,'2022-12-13');
  assert.doesNotMatch(JSON.stringify(out),/Future|Year only|2022-12-15/);
});
