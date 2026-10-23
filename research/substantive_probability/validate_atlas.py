"""Check catalogue references, runnable examples and public/private separation."""
from pathlib import Path
import importlib.util
import json
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
from legal_quant.scenarios import evaluate

def main():
    catalogue=json.loads((HERE/'catalogue.json').read_text('utf8'))
    entries=catalogue['entries']
    ids=[e['id'] for e in entries]
    assert len(ids)==len(set(ids))==19
    sources={s['id']:s for s in catalogue['sources']}
    assert len(sources)==len(catalogue['sources'])
    assert {e['id'] for e in entries if e['status']=='extension'}=={'scope_of_duty','loss_of_chance','reasonable_time'}
    for entry in entries:
        for field in ['title','legal_question','rule','formula','probability_meaning','formula_status','data','limits','example_note']:
            assert entry.get(field), (entry['id'],field)
        for sid in entry['source_ids']:
            assert sid in sources,(entry['id'],sid)
            assert sources[sid]['pin'] and sources[sid]['verification']
        sample=json.loads((HERE/'examples'/(entry['id']+'.json')).read_text('utf8'))
        assert sample==entry['example']['inputs']
        result=evaluate(entry['example']['kind'],sample)
        assert result['legal_conclusion'] is None
    spec=importlib.util.spec_from_file_location('atlas_renderer',HERE/'render_atlas.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    public=module.render_atlas(catalogue)
    assert 'class="calculation-error"' not in public
    assert '本地私有案卷映射版' not in public
    assert 'case-map"><h3>' not in public
    for private_token in ['HKIAC/A26045','DEXIN KONG','Dexin Kong','binance hkiac','OneDrive','matter-map.json']:
        assert private_token not in public, private_token
    generated=ROOT/'server/public/substantive-probability.html'
    assert generated.read_text('utf8')==public,'public HTML is stale; rerun renderer'
    mapping_path=HERE/'local/matter-map.json'
    mapping_count=0
    if mapping_path.exists():
        mapping=json.loads(mapping_path.read_text('utf8'))
        assert set(mapping)-{'_meta'}==set(ids)
        for entry_id in ids:
            assert mapping[entry_id]['soc'] and mapping[entry_id]['sod']
            assert mapping[entry_id]['fit'] and mapping[entry_id]['note']
        mapping_count=len(ids)
    print(json.dumps({'entries':len(ids),'sources':len(sources),'examples_passed':len(ids),'private_mappings_checked':mapping_count,'public_html_current':True,'legal_verdicts_generated':0},ensure_ascii=False))

if __name__=='__main__': main()
