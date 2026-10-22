"""Public artifact checks: privacy separation, real metric provenance and demo isolation."""
import json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
a=json.loads((R/'artifacts/results.json').read_text());w=json.loads((R/'web/experiment.json').read_text());d=json.loads((R/'web/demo-cases.json').read_text())
assert a['metrics']==w['metrics'] and a['routing']==w['routing']
assert len(d['samples'])==8 and len({r['id'] for r in d['samples']})==8
assert all(r['provenance']=='synthetic_demo' and 0<=r['score']<=1 for r in d['samples'])
assert all(r['inference']=='precomputed_actual_lightweight_model' for r in d['samples'])
assert all('text' not in r for r in w['errors'])
assert not any(p.suffix in ('.sqlite','.joblib','.csv') for p in (R/'web').rglob('*'))
assert d['samples'][1]['id']=='D02' and d['samples'][1]['route']=='block'
assert '/Users/' not in (R/'README.md').read_text()
assert all((R/'web/docs'/n).exists() for n in ['EXPERIMENT_REPORT.md','DATA_CARD.md','INTERVIEW_DEMO.md'])
print('Public Demo checks passed: metric parity, 8 isolated synthetic cases, no raw comments or DB/model exports.')
