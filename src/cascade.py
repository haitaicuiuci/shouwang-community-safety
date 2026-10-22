"""Composable cascade with no label input. A real adapter is opt-in by caller injection."""
def moderate(text,score,rule_hit,policy,adapter=None):
    version=policy['version']
    if score>=policy['block_threshold']:
        return dict(decision='block',stage='lightweight',policy_version=version,reason='high_score')
    if score<=policy['pass_threshold'] and not rule_hit:
        return dict(decision='pass',stage='lightweight',policy_version=version,reason='low_score')
    if adapter is None:
        return dict(decision='review',stage='human_queue',policy_version=version,reason='adapter_not_configured')
    result=adapter.review(text,version)
    # No oracle labels. Low-confidence and disabled/failure paths cannot auto-decide.
    if result['provenance'] in ('api','cache') and result['confidence']>=.9 and result['decision']!='review':
        return dict(decision=result['decision'],stage='llm',policy_version=version,reason=result['reason'])
    return dict(decision='review',stage='human_queue',policy_version=version,reason=result['provenance'])
