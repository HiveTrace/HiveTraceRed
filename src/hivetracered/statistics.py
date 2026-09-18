"""Prompt-level inference from harmful_attacks.ipynb (no category aggregates).

Errors are missing observations, never negative outcomes. Pairwise comparisons
use only prompts with valid observations for both the attack and NoneAttack.
"""
import ast
import json

import numpy as np
import pandas as pd


def _mapping(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        for parse in (json.loads, ast.literal_eval):
            try:
                result = parse(value)
                if isinstance(result, dict):
                    return result
            except (ValueError, SyntaxError, TypeError):
                pass
    return {}


def _present(value):
    if value is None or (not isinstance(value, (dict, list)) and pd.isna(value)):
        return False
    return bool(str(value).strip())


def _evaluation_failed(value):
    result = _mapping(value)
    return (any(_present(result.get(k)) for k in ('error', 'evaluation_error'))
            or _present(_mapping(result.get('raw_evaluation')).get('error'))
            or any(str(result.get(k, '')).lower() in ('error', 'ошибка')
                   for k in ('is_harmful', 'did_answer', 'should_answer', 'should_block')))


def error_mask(df):
    mask = pd.Series(False, index=df.index)
    for column in ('error', 'evaluation_error'):
        if column in df:
            mask |= df[column].map(_present)
    if 'evaluation' in df:
        mask |= df.evaluation.map(_evaluation_failed)
    return mask


def boolean_values(series):
    """Parse persisted booleans without interpreting the string 'False' as true."""
    return series.map(lambda v: str(v).strip().lower() in ('true', '1', '1.0'))


def valid_results(df):
    valid = df.loc[~error_mask(df)].copy()
    if 'success' in valid:
        valid = valid[valid.success.notna()].copy()
        valid['success'] = boolean_values(valid.success)
    if 'is_blocked' in valid:
        valid['is_blocked'] = boolean_values(valid.is_blocked)
    return valid


def prompt_means(df):
    key = 'base_prompt_id' if 'base_prompt_id' in df and df.base_prompt_id.notna().all() else 'base_prompt'
    keys = [c for c in ('dataset', 'attack_name', key) if c in df]
    return df.groupby(keys, dropna=False).success.mean() if keys else df.success

