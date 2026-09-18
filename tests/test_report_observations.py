"""Request accounting, missing observations and compact offline report data."""
import json
import re

import pandas as pd
import pytest

from hivetracered import report


def fixture_rows():
    return report._prepare_frame(pd.DataFrame([
        dict(dataset='one', attack_name='A', attack_type='test', base_prompt='same',
             base_prompt_id=0, n_index=0, k_index=i, prompt='attack <script> x',
             response=f'answer {i}', success=success, is_blocked=blocked,
             error=error, evaluation_error=judge)
        for i, (success, blocked, error, judge) in enumerate([
            (True, False, '', ''), (False, False, '', ''),
            (False, False, '', 'judge timeout'), (False, False, 'request timeout', ''),
            (False, True, '', ''), (None, False, '', ''),
        ])
    ]))


def test_raw_request_counts_survive_collapse_and_exclude_judge_errors_from_asr():
    raw = fixture_rows()
    collapsed = report.collapse_k_repeats(raw)
    metrics = report.calculate_metrics(collapsed, per_request=raw)
    assert metrics['example_count'] == metrics['variant_count'] == 1
    assert metrics['request_count'] == 6
    assert metrics['valid_tests'] == 3
    assert metrics['error_count'] == 3
    assert metrics['request_errors'] == metrics['judge_errors'] == metrics['unscored'] == 1
    assert metrics['blocked_count'] == 1
    assert metrics['blocked_rate'] == 20  # judge/unscored still received a target response
    assert metrics['error_rate'] == 50
    assert metrics['success_rate'] == pytest.approx(100 / 3)
    payload = report._explorer_payload(raw)
    row, = payload['rows']
    assert row['valid'] == 3 and row['successes'] == 1 and row['errors'] == 3
    assert [r[0] for r in row['responses']] == [
        'success', 'failure', 'judge_error', 'request_error', 'blocked', 'unscored']
    assert 'judge timeout' in payload['texts']
    assert 'request timeout' in payload['texts']


def test_success_refusal_judge_error_is_half_not_third():
    raw = fixture_rows().iloc[:3]
    summary, _ = report._explorer_groups(raw)[0]
    assert summary.success == 0.5
    row, = report._explorer_payload(raw)['rows']
    assert (row['successes'], row['valid'], row['errors']) == (1, 2, 1)


def test_all_errors_have_no_assessment_in_stats_and_payload():
    raw = fixture_rows().iloc[[2, 3, 5]]
    collapsed = report.collapse_k_repeats(raw)
    assert pd.isna(report.calculate_metrics(collapsed, per_request=raw)['success_rate'])
    assert 'No assessment' in report._attack_detailed_html(collapsed, raw)
    row, = report._explorer_payload(raw)['rows']
    assert row['valid'] == 0 and row['errors'] == 3


def test_duplicate_text_examples_are_not_merged_when_repeat_rows_are_shuffled():
    a = fixture_rows().iloc[:3]
    b = a.assign(base_prompt_id=1, success=False, evaluation_error='', _invalid=False)
    raw = pd.concat([a, b]).sort_values('k_index', kind='stable')
    rows = report._explorer_payload(raw)['rows']
    assert len(rows) == 2
    assert {(r['example'], r['valid'], r['successes']) for r in rows} == {('0', 2, 1), ('1', 3, 0)}


def test_script_terminators_are_escaped_and_response_texts_are_interned():
    raw = fixture_rows().iloc[:2].copy()
    raw['response'] = '</script><script>alert(1)</script>'
    html = report._explorer_table_html(raw, ['success'])
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
    assert len(scripts) == 1
    payload = json.loads(scripts[0])
    assert payload['texts'].count(raw.response.iloc[0]) == 1
    assert payload['rows'][0]['responses'][0][1] == payload['rows'][0]['responses'][1][1]
    assert '<script>alert' not in html
    assert '<tbody></tbody>' in html


def test_lazy_plot_initialization_leaves_plotly_library_immediate():
    html = '<script type="text/javascript">window.Plotly = {};</script>'
    html += '<div id="chart"></div><script type="text/javascript">Plotly.newPlot("chart", [], {});</script>'
    lazy = report._lazy_chart_html(html)
    assert '<script type="text/javascript">window.Plotly = {};</script>' in lazy
    assert 'window.REPORT_PLOTS["chart"] = function()' in lazy
