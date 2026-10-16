"""Known development mutations of derived JSON; frozen source bytes stay intact."""
import copy


def mutations(evaluation):
    def coherent_miss(e):
        c = e['cases'][0]
        c.update(classification='M', partition='M', first_hit_rank=None, confirmed_hit_rank=None,
                 reported_hit_rank=None, results=[], result_count=0)
        a = e['arms'][c['arm_id']]
        a['H'] -= 1
        a['M'] += 1
        a['delivered_hit_at_k'] = a['H'] / a['N']
        a['missingness_range'] = [a['H'] / a['N'], (a['H'] + a['U']) / a['N']]
    recipes = [
        ('missing_requested_pair', lambda e: e.update(pairs=[])),
        ('eligible_with_blocking_gates', lambda e: e['pairs'][0].update(comparison_status='eligible')),
        ('unsupported_decision', lambda e: e['decisions']['a'].update(decision_status='meets_criteria')),
        ('fabricated_zero_cost', lambda e: e['arms']['a']['cost'].update(total='0', support_status='supported', unavailable_reason=None)),
        ('duplicate_requested_pair', lambda e: e['pairs'].append(copy.deepcopy(e['pairs'][0]))),
        ('extra_unrequested_pair', lambda e: e['pairs'].append(dict(e['pairs'][0], arm_a='b', arm_b='a'))),
        ('coherent_hit_to_miss', coherent_miss),
        ('altered_rank', lambda e: e['cases'][0].update(first_hit_rank=2, confirmed_hit_rank=2)),
        ('altered_result', lambda e: e['cases'][0]['results'][0].update(url='https://example.org/fabricated')),
        ('altered_settings', lambda e: e['arms']['a']['settings']['actual'].update(mode='invented')),
        ('altered_source_inventory', lambda e: e['source_inventory'][0].update(sha256='0' * 64)),
        ('forged_reference_status', lambda e: e['reference_checks'][1].update(status='passed', reason=None)),
        ('fabricated_latency', lambda e: e['arms']['a']['latency'].update(paired=[], support_status='supported', unavailable_reason=None)),
        ('changed_criteria', lambda e: e['decisions']['a'].update(criteria={'min_delivered_hit_rate': 0})),
        ('removed_diagnostics', lambda e: e.update(diagnostics=[])),
        ('removed_gates_and_diagnostics', lambda e: (e.update(diagnostics=[]), e['pairs'][0].update(comparison_status='eligible', gates=[]))),
        ('altered_attempt', lambda e: e['cases'][0]['attempts'][0].update(latency_ms=123)),
        ('altered_retry_selection', lambda e: e['cases'][0].update(selected_attempt_id='later-invented-hit')),
        ('altered_query', lambda e: e['cases'][0].update(query_text='not the source query')),
        ('altered_source_ref', lambda e: e['cases'][0].update(source_refs=[])),
        ('altered_native_metric', lambda e: e['native_metrics']['a'].update(recall_at_k=0)),
        ('altered_limitation', lambda e: e.update(limitations=[])),
        ('extra_claim', lambda e: e.update(provider_winner='a')),
    ]
    for name, recipe in recipes:
        value = copy.deepcopy(evaluation)
        recipe(value)
        yield name, value
