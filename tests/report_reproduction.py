"""Report platform drift explicitly; do not overwrite the frozen public experiment."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
reference = json.loads((root/'web/experiment.json').read_text())
current = json.loads((root/'artifacts/results.json').read_text())
# Structural/data invariants must hold. Model scores are reported separately.
assert reference['quality']['retained_counts'] == current['quality']['retained_counts']
assert current['quality']['cross_split_groups_after'] == 0
assert current['routing']['actual_llm_calls'] == 0
assert sum(current['routing']['counts'].values()) == current['routing']['n']
comparison = {
    'interpretation': 'Pipeline checks do not certify identical cross-platform model outputs.',
    'reference_environment': reference['environment'],
    'current_environment': current['environment'],
    'reference_policy': reference['policy'],
    'current_policy': current['policy'],
    'reference_metrics': reference['metrics'],
    'current_metrics': current['metrics'],
    'reference_routing': reference['routing'],
    'current_routing': current['routing'],
    'exact_metrics_match': reference['metrics'] == current['metrics'],
    'exact_routing_match': reference['routing'] == current['routing'],
}
(root/'artifacts/ci_comparison.json').write_text(json.dumps(comparison, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(comparison, ensure_ascii=False, indent=2))
