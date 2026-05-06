# Fix the f-string issue by building the attribute string separately and re-writing the file.

import os, json, argparse
from datetime import datetime
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.io as pio
from hivetracered.pipeline.framework_mapping import (
    FRAMEWORKS,
    get_framework_mappings,
)
from hivetracered.pipeline.mitigations import get_prioritized_mitigations

SUCCESS_RATE = "Success Rate"
ATTACK_TYPE = "Attack Type"
TOTAL_TESTS = "Total Tests"
BLOCK_RATE = "Block Rate"

def get_chart_style():
    return {
        "paper_bgcolor": "#161a23",
        "plot_bgcolor": "#161a23",
        "font": dict(color="#e8e8e8"),
        "xaxis": dict(gridcolor="#2a2f3a", color="#e8e8e8"),
        "yaxis": dict(gridcolor="#2a2f3a", color="#e8e8e8")
    }

def _read_dataframe(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.parquet':
        return pd.read_parquet(file_path)
    if ext in ('.xlsx', '.xls'):
        return pd.read_excel(file_path)
    return pd.read_csv(file_path)


def _safe_get(d, key, default="unknown"):
    if isinstance(d, dict):
        return d.get(key, default)
    try:
        dd = json.loads(d)
    except Exception:
        return default
    if isinstance(dd, dict):
        return dd.get(key, default)
    return default


def _expand_evaluation(df):
    for key in ("is_harmful", "did_answer", "should_block"):
        df[key] = df["evaluation"].apply(lambda x, k=key: _safe_get(x, k))


def load_data(file_path="df.csv"):
    try:
        df = _read_dataframe(file_path)
    except Exception as e:
        print(f"Error loading data: {e}")
        return pd.DataFrame()

    if "evaluation" in df.columns:
        _expand_evaluation(df)

    for col in ("success", "is_blocked"):
        if col in df.columns:
            df[col] = df[col].astype(bool)

    if "response" in df.columns:
        df["response_length"] = df["response"].fillna("").astype(str).str.len()

    return df

def _basic_rates(df):
    has_rows = len(df) > 0
    total_tests = len(df) if has_rows else 0
    success_rate = float(df["success"].mean() * 100) if "success" in df.columns and has_rows else 0.0
    blocked_rate = float(df["is_blocked"].mean() * 100) if "is_blocked" in df.columns and has_rows else 0.0
    error_count = (
        int(((df["error"].notna()) & (df["error"] != "")).sum())
        if "error" in df.columns and has_rows else 0
    )
    error_rate = float(error_count / len(df) * 100) if has_rows else 0.0
    return total_tests, success_rate, blocked_rate, error_rate


def _best_attack(df):
    if not ("attack_name" in df.columns and "success" in df.columns and len(df)):
        return "-", 0.0
    g = df.groupby("attack_name")["success"].agg(["count", "sum", "mean"]).reset_index()
    if not len(g):
        return "-", 0.0
    idx = g["mean"].idxmax()
    return str(g.loc[idx, "attack_name"]), float(g.loc[idx, "mean"] * 100)


def _vulnerable_prompts(df):
    if not ("base_prompt" in df.columns and "success" in df.columns and len(df)):
        return 0, 0, 0.0
    vulnerable = int(df.loc[df["success"] == True, "base_prompt"].nunique())
    total = int(df["base_prompt"].nunique())
    rate = float(vulnerable / total * 100) if total > 0 else 0.0
    return vulnerable, total, rate


def _merge_mappings(df, base_category, subcategories):
    if "attack_type" in df.columns and "attack_name" in df.columns and len(df):
        merged: dict = {}
        pairs = df[["attack_type", "attack_name"]].drop_duplicates()
        for _, row in pairs.iterrows():
            m = get_framework_mappings(
                attack_type=row["attack_type"],
                attack_name=row["attack_name"],
                base_category=base_category,
                subcategories=subcategories,
            )
            for fw, cats in m.items():
                merged.setdefault(fw, set()).update(cats)
        return merged
    return get_framework_mappings(base_category=base_category, subcategories=subcategories)


def _framework_categories(merged_mappings):
    framework_categories: dict = {}
    for fw_key, cat_ids in merged_mappings.items():
        fw_defs = FRAMEWORKS.get(fw_key, {}).get("categories", {})
        framework_categories[fw_key] = sorted(
            f"{cid}: {fw_defs[cid]['name']}" for cid in cat_ids if cid in fw_defs
        )
    return framework_categories


def _asr_none_attack(df):
    if not ("attack_name" in df.columns and "success" in df.columns and len(df)):
        return 0.0
    none_attack_df = df[df["attack_name"] == "NoneAttack"]
    if len(none_attack_df) == 0:
        return 0.0
    return float(none_attack_df["success"].mean() * 100)


def _asr_max_injection(df):
    if not ("attack_name" in df.columns and "success" in df.columns and len(df)):
        return 0.0, "-"
    injection_df = df[df["attack_name"] != "NoneAttack"]
    if len(injection_df) == 0:
        return 0.0, "-"
    attack_stats = injection_df.groupby("attack_name")["success"].mean()
    if len(attack_stats) == 0:
        return 0.0, "-"
    return float(attack_stats.max() * 100), str(attack_stats.idxmax())


def _vulnerable_attack_types(df):
    if not ("attack_type" in df.columns and "success" in df.columns and len(df)):
        return []
    type_asr = df.groupby("attack_type")["success"].mean()
    return sorted(type_asr[type_asr > 0].index.tolist())


def calculate_metrics(df):
    total_tests, success_rate, blocked_rate, error_rate = _basic_rates(df)

    has_rows = len(df) > 0
    model_name = df["model"].iloc[0] if "model" in df.columns and has_rows else "Unknown"
    n_attack_types = df["attack_type"].nunique() if "attack_type" in df.columns else 0
    n_attacks = df["attack_name"].nunique() if "attack_name" in df.columns else 0

    best_attack_name, best_attack_rate = _best_attack(df)
    vulnerable_prompts, total_prompts, vulnerable_prompts_rate = _vulnerable_prompts(df)

    base_category = df["category"].iloc[0] if "category" in df.columns and has_rows else "Unknown"
    subcategories = df["subcategory"].unique().tolist() if "subcategory" in df.columns else None

    merged_mappings = _merge_mappings(df, base_category, subcategories)
    framework_categories = _framework_categories(merged_mappings)

    asr_none_attack = _asr_none_attack(df)
    asr_max_attack, best_attack_name_detailed = _asr_max_injection(df)

    vulnerable_attack_types = _vulnerable_attack_types(df)
    prioritized_mitigations = get_prioritized_mitigations(vulnerable_attack_types)

    return {
        "total_tests": total_tests, "success_rate": success_rate, "blocked_rate": blocked_rate,
        "error_rate": error_rate, "model_name": model_name, "n_attack_types": n_attack_types,
        "n_attacks": n_attacks, "best_attack_name": best_attack_name, "best_attack_rate": best_attack_rate,
        "vulnerable_prompts": vulnerable_prompts, "total_prompts": total_prompts,
        "vulnerable_prompts_rate": vulnerable_prompts_rate,
        "base_category": base_category,
        "framework_categories": framework_categories,
        "framework_mappings": {k: sorted(v) for k, v in merged_mappings.items()},
        "asr_none_attack": asr_none_attack, "asr_max_attack": asr_max_attack,
        "best_attack_name_detailed": best_attack_name_detailed,
        "vulnerable_attack_types": vulnerable_attack_types,
        "prioritized_mitigations": prioritized_mitigations,
    }

def _per_type_stats(df, include_block_rate=False):
    type_stats = []
    for attack_type in df["attack_type"].unique():
        type_df = df[df["attack_type"] == attack_type]
        total_unique_prompts = type_df["base_prompt"].nunique()
        successful_prompts = type_df[type_df["success"] == True]["base_prompt"].nunique()
        success_rate = successful_prompts / total_unique_prompts if total_unique_prompts > 0 else 0.0
        entry = {
            "attack_type": attack_type,
            SUCCESS_RATE: success_rate * 100 if include_block_rate else success_rate,
            "Total Unique Prompts": total_unique_prompts,
            "Successful Prompts": successful_prompts,
        }
        if include_block_rate:
            entry[BLOCK_RATE] = type_df["is_blocked"].mean() * 100
        type_stats.append(entry)
    return type_stats


def _build_top_types_html(df):
    if not {"attack_type", "success", "attack_name", "base_prompt"}.issubset(df.columns):
        return ""
    top_types = pd.DataFrame(_per_type_stats(df))
    top_types[SUCCESS_RATE] = top_types[SUCCESS_RATE] * 100
    top_types = top_types.sort_values(SUCCESS_RATE, ascending=False).head(3).reset_index(drop=True)
    fig_top_types = px.bar(
        top_types, x=SUCCESS_RATE, y="attack_type", orientation="h",
        text=SUCCESS_RATE
    )
    fig_top_types.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_top_types.update_layout(
        xaxis_title="Success Rate (% of Unique Prompts)", yaxis_title=ATTACK_TYPE, height=350, margin={"l": 10, "r": 10, "t": 30, "b": 10},
        **get_chart_style()
    )
    return pio.to_html(fig_top_types, include_plotlyjs=True, full_html=False)


def _build_top_attacks_html(df, include_plotlyjs):
    if not {"attack_name", "success"}.issubset(df.columns):
        return ""
    top_attacks = (
        df.groupby("attack_name")["success"]
          .agg(["count","sum","mean"]).rename(columns={"count":TOTAL_TESTS,"sum":"Successes","mean":SUCCESS_RATE})
    )
    top_attacks[SUCCESS_RATE] = top_attacks[SUCCESS_RATE] * 100
    top_attacks = top_attacks.sort_values(SUCCESS_RATE, ascending=False).head(3).reset_index()
    fig_top_attacks = px.bar(
        top_attacks, x=SUCCESS_RATE, y="attack_name", orientation="h",
        text=SUCCESS_RATE
    )
    fig_top_attacks.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_top_attacks.update_layout(
        xaxis_title="Success Rate (%)", yaxis_title="Attack Name", height=350, margin=dict(l=10,r=10,t=30,b=10),
        **get_chart_style()
    )
    return pio.to_html(fig_top_attacks, include_plotlyjs=include_plotlyjs, full_html=False)


def _build_attack_type_html(df):
    if not {"attack_type","success","is_blocked","attack_name","base_prompt"}.issubset(df.columns):
        return ""
    attack_type_stats = pd.DataFrame(_per_type_stats(df, include_block_rate=True))
    attack_type_stats = attack_type_stats[attack_type_stats[SUCCESS_RATE] > 3]
    if len(attack_type_stats) == 0:
        return "<p style='color: var(--muted); text-align: center; padding: 40px;'>No attack types with success rate > 3%</p>"
    fig_attack_type = px.bar(attack_type_stats, x="attack_type", y=SUCCESS_RATE)
    fig_attack_type.update_layout(
        xaxis_title=ATTACK_TYPE, yaxis_title="Success Rate (% of Unique Prompts)", height=400, margin={"l": 10, "r": 10, "t": 30, "b": 10},
        **get_chart_style()
    )
    return pio.to_html(fig_attack_type, include_plotlyjs=False, full_html=False)


def _build_attacks_html(df):
    if not {"attack_name","success","is_blocked"}.issubset(df.columns):
        return ""
    attack_stats = (
        df.groupby("attack_name")
        .agg({"success":["count","sum","mean"], "is_blocked":"mean"})
    )
    attack_stats.columns = [TOTAL_TESTS,"Successes",SUCCESS_RATE,BLOCK_RATE]
    attack_stats[SUCCESS_RATE] = attack_stats[SUCCESS_RATE] * 100
    attack_stats[BLOCK_RATE] = attack_stats[BLOCK_RATE] * 100
    attack_stats = attack_stats.reset_index()
    attack_stats = attack_stats[attack_stats[SUCCESS_RATE] > 3]
    if len(attack_stats) == 0:
        return "<p style='color: var(--muted); text-align: center; padding: 40px;'>No individual attacks with success rate > 3%</p>"
    fig_attacks = px.bar(attack_stats, x="attack_name", y=SUCCESS_RATE)
    fig_attacks.update_layout(
        xaxis_title="Attack Name", yaxis_title="Success Rate (%)", xaxis_tickangle=45, height=500, margin=dict(l=10,r=10,t=30,b=50),
        **get_chart_style()
    )
    return pio.to_html(fig_attacks, include_plotlyjs=False, full_html=False)


def _build_length_charts_html(df):
    if not {"response_length","success","attack_type"}.issubset(df.columns):
        return "", ""
    fig_length = px.box(df, x="success", y="response_length", color="success")
    fig_length.update_layout(
        xaxis_title="Attack Success", yaxis_title="Response Length (chars)", height=400, margin=dict(l=10,r=10,t=30,b=10),
        **get_chart_style()
    )
    length_html = pio.to_html(fig_length, include_plotlyjs=False, full_html=False)

    avg_length = df.groupby("attack_type")["response_length"].mean().reset_index()
    fig_avg_length = px.bar(avg_length, x="attack_type", y="response_length")
    fig_avg_length.update_layout(
        xaxis_title=ATTACK_TYPE, yaxis_title="Avg Response Length (chars)", xaxis_tickangle=45, height=400, margin={"l": 10, "r": 10, "t": 30, "b": 50},
        **get_chart_style()
    )
    avg_length_html = pio.to_html(fig_avg_length, include_plotlyjs=False, full_html=False)
    return length_html, avg_length_html


def _build_answer_html(df):
    if not ({"did_answer","success"}.issubset(df.columns) and len(df)):
        return ""
    answer_analysis = pd.crosstab(df["did_answer"], df["success"], normalize="index") * 100
    answer_long = answer_analysis.reset_index().melt(id_vars="did_answer", var_name="success", value_name="pct")
    fig_answer = px.bar(answer_long, x="did_answer", y="pct", color="success", barmode="stack")
    fig_answer.update_layout(
        xaxis_title="Did Answer", yaxis_title="Percentage", height=400, margin=dict(l=10,r=10,t=30,b=10),
        **get_chart_style()
    )
    return pio.to_html(fig_answer, include_plotlyjs=False, full_html=False)


def create_charts(df):
    fig_top_types_html = _build_top_types_html(df)
    fig_top_attacks_html = _build_top_attacks_html(df, include_plotlyjs=not fig_top_types_html)
    fig_attack_type_html = _build_attack_type_html(df)
    fig_attacks_html = _build_attacks_html(df)
    fig_length_html, fig_avg_length_html = _build_length_charts_html(df)
    fig_answer_html = _build_answer_html(df)

    return {
        "fig_top_types_html": fig_top_types_html,
        "fig_top_attacks_html": fig_top_attacks_html,
        "fig_attack_type_html": fig_attack_type_html,
        "fig_attacks_html": fig_attacks_html,
        "fig_length_html": fig_length_html,
        "fig_avg_length_html": fig_avg_length_html,
        "fig_answer_html": fig_answer_html
    }

def _attack_detailed_html(df):
    if not {"attack_type","attack_name","success","is_blocked"}.issubset(df.columns):
        return ""
    attack_detailed = (
        df.groupby(["attack_type","attack_name"])
        .agg({
            "success":["count","sum","mean"],
            "is_blocked":"mean",
            "error": lambda x: (x.notna() & (x != "")).sum() if "error" in df.columns else 0
        })
    )
    attack_detailed.columns = [TOTAL_TESTS,"Successes",SUCCESS_RATE,BLOCK_RATE,"Errors"]
    attack_detailed[SUCCESS_RATE] = attack_detailed[SUCCESS_RATE] * 100
    attack_detailed[BLOCK_RATE] = attack_detailed[BLOCK_RATE] * 100
    attack_detailed = attack_detailed.reset_index()
    attack_detailed[SUCCESS_RATE] = attack_detailed[SUCCESS_RATE].round(1).astype(str) + "%"
    attack_detailed[BLOCK_RATE] = attack_detailed[BLOCK_RATE].round(1).astype(str) + "%"
    return attack_detailed.to_html(index=False, classes="dataframe compact", border=0)


def _bfmt(x):
    if isinstance(x, (bool, np.bool_)):
        return "✅" if x else "❌"
    return str(x)


def _explorer_row_html(r, display_columns):
    attrs = {
        "data-attack-type": str(r.get("attack_type","")),
        "data-success": str(r.get("success","")).lower(),
        "data-blocked": str(r.get("is_blocked","")).lower()
    }
    attrs_str = " ".join([f'{k}="{v}"' for k, v in attrs.items()])
    tds = "".join(f"<td>{_bfmt(r[c])}</td>" for c in display_columns)
    return f"<tr {attrs_str}>{tds}</tr>"


def _explorer_table_html(df, display_columns):
    explorer_table_rows = []
    if display_columns:
        for _, r in df[display_columns].fillna("").iterrows():
            explorer_table_rows.append(_explorer_row_html(r, display_columns))
    return f"""
    <div class="table-container">
      <table id="explorer-table" class="dataframe compact">
        <thead>
          <tr>{''.join(f'<th>{c}</th>' for c in display_columns)}</tr>
        </thead>
        <tbody>
          {''.join(explorer_table_rows)}
        </tbody>
      </table>
    </div>
    """


def _sample_block_html(row):
    title = f"{row.get('attack_name','Unknown')} - {'✅ Success' if bool(row.get('success', False)) else '❌ Failed'}"
    bp = str(row.get("base_prompt","N/A"))
    pr = str(row.get("prompt","N/A"))
    rs = str(row.get("response","N/A"))
    return f"""
    <details class="sample-block">
      <summary>{title}</summary>
      <div class="sample-inner">
        <h4>Base Prompt</h4>
        <pre>{bp}</pre>
        <h4>Attack Prompt</h4>
        <pre>{pr}</pre>
        <h4>Model Response</h4>
        <pre>{rs}</pre>
      </div>
    </details>
    """


def _samples_html(df):
    if not ({"attack_name","success","base_prompt","prompt","response"}.issubset(df.columns) and len(df)):
        return ""
    sample_pool = df[df["success"] == True]
    if len(sample_pool) == 0:
        sample_pool = df
    sample_df = sample_pool.sample(min(5, len(sample_pool)), random_state=7)
    blocks = [_sample_block_html(row) for _, row in sample_df.iterrows()]
    return "\n".join(blocks)


def generate_data_tables(df):
    attack_detailed_html = _attack_detailed_html(df)
    display_columns = [c for c in ["attack_name","attack_type","success","is_blocked"] if c in df.columns]
    explorer_table_html = _explorer_table_html(df, display_columns)
    samples_html = _samples_html(df)

    return {
        "attack_detailed_html": attack_detailed_html,
        "explorer_table_html": explorer_table_html,
        "samples_html": samples_html,
        "display_columns": display_columns
    }


def build_html_report(df, metrics, charts, data_tables):
    """
    Build complete HTML report from processed data.

    Args:
        df: DataFrame with evaluation results
        metrics: Dictionary of calculated metrics
        charts: Dictionary of chart HTML strings
        data_tables: Dictionary of data table HTML strings

    Returns:
        Complete HTML string for the report
    """
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    styles = """
    <style>
    :root{
      --bg: #0e1117;
      --card: #161a23;
      --text: #e8e8e8;
      --muted: #b0b8c3;
      --accent: #ff4b4b;
      --accent2: #ffa14b;
      --border: #2a2f3a;
      --good: #22c55e;
      --warn: #f59e0b;
    }
    * { box-sizing: border-box; }
    body{
      margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji";
      background: var(--bg); color: var(--text);
    }
    .wrapper{ max-width: 1200px; margin: 0 auto; padding: 24px; }
    h1{ font-size: 28px; margin: 0 0 8px; }
    h2{ font-size: 22px; margin: 24px 0 8px; }
    h3{ font-size: 18px; margin: 16px 0 8px; color: var(--muted); }
    .section{ background: var(--card); border: 1px solid var(--border); padding: 16px; border-radius: 16px; margin-bottom: 16px; }
    .grid-4{ display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; }
    .grid-2{ display:grid; grid-template-columns: repeat(2, 1fr); gap:12px; }
    .metric{
      background: #121620; border: 1px solid var(--border);
      padding:16px; border-radius: 12px;
    }
    .metric .label{ color: var(--muted); font-size: 13px; }
    .metric .value{ font-size: 24px; font-weight:600; margin-top:4px; }
    .metric .delta{ color: var(--muted); font-size: 12px; margin-top:2px; }
    .kf{ display:flex; gap:12px; flex-wrap: wrap;}
    .kf .badge{ padding: 10px 12px; background:#102116; border:1px solid #1b3a26; color:#9be3b4; border-radius:10px; }
    .kf .warn{ background:#211d10; border-color:#3a2f1b; color:#ffd29b; }
    hr{ border: none; border-top: 1px solid var(--border); margin: 20px 0; }

    .tabs{ display:flex; gap:6px; margin: 12px 0 16px; flex-wrap: wrap;}
    .tablink{
      background: transparent; color: var(--text); border:1px solid var(--border);
      padding:8px 12px; border-radius:999px; cursor:pointer;
    }
    .tablink.active{ background: var(--accent); border-color: var(--accent); }

    table.dataframe{ width:100%; border-collapse: collapse; }
    table.dataframe th, table.dataframe td{ border-bottom:1px solid var(--border); padding:8px; text-align:left; }
    table.dataframe tr:hover{ background: #0f1420; }
    .compact th, .compact td{ font-size: 13px; }

    .table-container{ max-height: 600px; overflow-y: auto; border: 1px solid var(--border); border-radius: 8px; }
    .table-container table{ margin: 0; border-radius: 0; }

    .sample-block{ margin: 8px 0; }
    .sample-block summary{ cursor:pointer; list-style: none; border:1px solid var(--border); background:#0f1420; padding:10px 12px; border-radius:10px; }
    .sample-block summary::-webkit-details-marker{ display:none; }
    .sample-inner{ padding:10px 2px; }
    pre{ white-space: pre-wrap; background:#0b0f19; padding:10px; border: 1px solid var(--border); border-radius: 8px; }

    .controls{ display:grid; grid-template-columns: 1fr 1fr 1fr; gap:12px; margin-bottom: 10px; }
    .control{ background:#0f1420; border:1px solid var(--border); padding:10px; border-radius:10px; }
    .checkbox-group{ display:flex; flex-wrap: wrap; gap:8px; max-height: 120px; overflow:auto; }
    .checkbox-group label{ background:#0b0f19; border:1px solid var(--border); padding:6px 8px; border-radius:8px; display:flex; align-items:center; gap:6px; }
    .select{ width:100%; padding:8px; background:#0b0f19; border:1px solid var(--border); color:var(--text); border-radius:8px; }

    .footer{ color: var(--muted); font-size: 12px; text-align:center; margin-top: 28px; }

    .plot-container{ width: 100%; display: flex; justify-content: center; margin: 16px 0; }
    .plot-container > div{ width: 100%; max-width: 100%; }

    .mitigation-item{
      background: #0f1420; border: 1px solid var(--border); padding: 14px 16px;
      border-radius: 12px; margin-bottom: 10px; display: flex; align-items: center; gap: 16px;
    }
    .mitigation-item .mit-name{ flex: 1; font-weight: 500; }
    .mitigation-item .mit-coverage{ color: var(--muted); font-size: 13px; white-space: nowrap; }
    .progress-bar{
      width: 120px; height: 8px; background: #1a1f2e; border-radius: 4px; overflow: hidden; flex-shrink: 0;
    }
    .progress-bar .fill{ height: 100%; border-radius: 4px; background: var(--good); transition: width 0.3s; }
    .mitigation-badge{
      display: inline-block; padding: 4px 10px; margin: 3px 4px 3px 0; font-size: 12px;
      background: #102116; border: 1px solid #1b3a26; color: #9be3b4; border-radius: 8px;
    }
    </style>
    """

    attack_types_unique = sorted(df["attack_type"].dropna().unique().tolist()) if "attack_type" in df.columns else []
    controls_js = f"""
    <script>
    function showTab(id) {{
      document.querySelectorAll('.section').forEach(s => s.style.display='none');
      document.getElementById(id).style.display = 'block';
      document.querySelectorAll('.tablink').forEach(b => b.classList.remove('active'));
      document.querySelector('[data-target="'+id+'"]').classList.add('active');
      // Trigger Plotly resize for responsive charts
      setTimeout(function() {{
        if (window.Plotly) {{
          document.querySelectorAll('#' + id + ' .plotly-graph-div').forEach(function(gd) {{
            window.Plotly.Plots.resize(gd);
          }});
        }}
      }}, 100);
    }}
    document.addEventListener('DOMContentLoaded', function(){{
      showTab('tab1');
      // Initialize responsive charts
      setTimeout(function() {{
        if (window.Plotly) {{
          document.querySelectorAll('.plotly-graph-div').forEach(function(gd) {{
            window.Plotly.Plots.resize(gd);
          }});
        }}
      }}, 500);
      const ctn = document.getElementById('attack-type-box');
      const types = {json.dumps(attack_types_unique)};
      types.forEach(t => {{
        const id = 'chk_' + t.replace(/\\W+/g,'_');
        const wrap = document.createElement('label');
        const cb = document.createElement('input');
        cb.type = 'checkbox'; cb.checked = true; cb.id = id; cb.value = t;
        wrap.appendChild(cb);
        wrap.appendChild(document.createTextNode(' ' + t));
        ctn.appendChild(wrap);
      }});

      document.getElementById('filter-success').addEventListener('change', filterTable);
      document.getElementById('filter-blocked').addEventListener('change', filterTable);
      ctn.addEventListener('change', filterTable);
      filterTable();
    }});

    function filterTable(){{
      const rows = document.querySelectorAll('#explorer-table tbody tr');
      const successSel = document.getElementById('filter-success').value;
      const blockedSel = document.getElementById('filter-blocked').value;

      const allowed = Array.from(document.querySelectorAll('#attack-type-box input[type="checkbox"]'))
        .filter(cb => cb.checked).map(cb => cb.value);

      rows.forEach(r => {{
        const at = r.getAttribute('data-attack-type');
        const sc = r.getAttribute('data-success');
        const bl = r.getAttribute('data-blocked');

        let ok = true;
        if (allowed.indexOf(at) === -1) ok = false;
        if (successSel === 'success' && sc !== 'true') ok = false;
        if (successSel === 'fail' && sc !== 'false') ok = false;
        if (blockedSel === 'blocked' && bl !== 'true') ok = false;
        if (blockedSel === 'not_blocked' && bl !== 'false') ok = false;

        r.style.display = ok ? '' : 'none';
      }});

      const visible = Array.from(rows).filter(r => r.style.display !== 'none').length;
      document.getElementById('filtered-count').innerText = visible + ' records';
    }}
    </script>
    """

    controls_html = f"""
    <div class="controls">
      <div class="control">
        <div style="font-size:12px; color: var(--muted); margin-bottom:6px;">Filter by Attack Type</div>
        <div id="attack-type-box" class="checkbox-group"></div>
      </div>
      <div class="control">
        <div style="font-size:12px; color: var(--muted); margin-bottom:6px;">Filter by Success</div>
        <select id="filter-success" class="select">
          <option value="all">All</option>
          <option value="success">Successful Only</option>
          <option value="fail">Failed Only</option>
        </select>
      </div>
      <div class="control">
        <div style="font-size:12px; color: var(--muted); margin-bottom:6px;">Filter by Blocked Status</div>
        <select id="filter-blocked" class="select">
          <option value="all">All</option>
          <option value="blocked">Blocked Only</option>
          <option value="not_blocked">Not Blocked Only</option>
        </select>
      </div>
    </div>
    """

    # Build per-framework category badges HTML
    fw_short = {
        "OWASP_LLM_TOP_10": "OWASP LLM Top 10",
        "MITRE_ATLAS": "MITRE ATLAS",
        "FSTEK_117": "ФСТЭК 117",
    }
    fw_badge_colors = {
        "OWASP_LLM_TOP_10": ("#9bb4e3", "#1a1e3a", "#2a3a5a"),
        "MITRE_ATLAS": ("#9be3b4", "#102116", "#1b3a26"),
        "FSTEK_117": ("#ffd29b", "#211d10", "#3a2f1b"),
    }
    framework_categories = metrics.get("framework_categories", {})
    framework_badges_html = ""
    for fw_key in ["OWASP_LLM_TOP_10", "MITRE_ATLAS", "FSTEK_117"]:
        cats = framework_categories.get(fw_key, [])
        if not cats:
            continue
        fw_name = fw_short.get(fw_key, fw_key)
        color, bg, border = fw_badge_colors.get(fw_key, ("#e8e8e8", "#1a1e3a", "#2a3a5a"))
        fw_defs = FRAMEWORKS.get(fw_key, {}).get("categories", {})
        badges = []
        for cat in cats:
            cat_id = cat.split(":")[0].strip()
            desc = fw_defs.get(cat_id, {}).get("description", "")
            badges.append(
                f'<div class="badge" style="background:{bg}; border-color:{border}; color:{color};" title="{desc}">{cat}</div>'
            )
        framework_badges_html += f"""
          <div style="margin-bottom:8px;"><strong>{fw_name}:</strong></div>
          <div class="kf" style="margin-bottom:12px;">
            {chr(10).join(badges)}
          </div>
"""

    # Build mitigations tab HTML
    mitigations_html = ""
    prioritized = metrics.get("prioritized_mitigations", [])
    if prioritized:
        items = []
        for m in prioritized:
            pct = int(m["covers"] / m["total"] * 100) if m["total"] else 0
            items.append(
                f'<div class="mitigation-item">'
                f'<div class="mit-name">{m["mitigation"]}</div>'
                f'</div>'
            )
        mitigations_html += "<h3>Prioritized Mitigations</h3>\n" + "\n".join(items)
    else:
        mitigations_html += '<p style="color:var(--muted);padding:20px;">No vulnerable attack types detected — no mitigations to recommend.</p>'

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Static Report</title>
    {styles}
    </head>
    <body>
    <div class="wrapper">
      <h1>🔍 Automated Report</h1>
      <div style="color:var(--muted);">Comprehensive analysis of red teaming results</div>

      <div class="tabs">
        <button class="tablink active" data-target="tab1" onclick="showTab('tab1')">📋 Executive Summary</button>
        <button class="tablink" data-target="tab2" onclick="showTab('tab2')">⚔️ Attack Analysis</button>
        <button class="tablink" data-target="tab3" onclick="showTab('tab3')">📝 Content Analysis</button>
        <button class="tablink" data-target="tab4" onclick="showTab('tab4')">🔍 Data Explorer</button>
        <button class="tablink" data-target="tab5" onclick="showTab('tab5')">🛡️ Mitigations</button>
      </div>

      <!-- Executive Summary -->
      <div id="tab1" class="section">
        <h2>🎯 Executive Summary</h2>
        <div class="grid-4">
          <div class="metric">
            <div class="label">Total Tests</div>
            <div class="value">{metrics['total_tests']}</div>
          </div>
          <div class="metric">
            <div class="label">Success Rate</div>
            <div class="value">{metrics['success_rate']:.1f}%</div>
          </div>
          <div class="metric">
            <div class="label">Blocked Rate</div>
            <div class="value">{metrics['blocked_rate']:.1f}%</div>
          </div>
          <div class="metric">
            <div class="label">Error Rate</div>
            <div class="value">{metrics['error_rate']:.1f}%</div>
          </div>
        </div>

        <h3>🔍 Key Findings</h3>
        <div class="kf">
          <div class="badge">Most Effective Attack: <strong>{metrics['best_attack_name']}</strong> ({metrics['best_attack_rate']:.1f}% ASR)</div>
          <div class="badge warn">Vulnerable Prompts: <strong>{metrics['vulnerable_prompts']}/{metrics['total_prompts'] or 0}</strong> ({metrics['vulnerable_prompts_rate']:.1f}%)</div>
        </div>

        <h3>📊 Security Framework Coverage</h3>
        <div style="background:#0f1420; border:1px solid var(--border); padding:16px; border-radius:12px; margin-bottom:16px;">
          <div style="margin-bottom:12px;"><strong>Category:</strong> <span style="color:var(--accent2);">{metrics.get('base_category', 'Unknown')}</span></div>
          {framework_badges_html if framework_badges_html else '<div style="color:var(--muted);">No framework categories mapped</div>'}
        </div>

        <h3>🎯 Attack Success Rate (ASR) Analysis</h3>
        <div class="grid-2">
          <div class="metric">
            <div class="label">ASR without Prompt Injections</div>
            <div class="value" style="color:var(--good);">{metrics.get('asr_none_attack', 0.0):.1f}%</div>
            <div class="delta">Average for NoneAttack - baseline vulnerability</div>
          </div>
          <div class="metric">
            <div class="label">ASR with Prompt Injections</div>
            <div class="value" style="color:var(--accent);">{metrics.get('asr_max_attack', 0.0):.1f}%</div>
            <div class="delta">Average for {metrics.get('best_attack_name_detailed', '-')}</div>
          </div>
        </div>

        <h3>Top 3 Most Successful Attack Types</h3>
        <div style="color:var(--muted); font-size:13px; margin-bottom:8px;">Based on unique prompts that succeeded in at least one attack of this type</div>
        {charts['fig_top_types_html']}

        <h3>Top 3 Most Successful Individual Attacks</h3>
        {charts['fig_top_attacks_html']}

      </div>

      <!-- Attack Analysis -->
      <div id="tab2" class="section" style="display:none;">
        <h2>⚔️ Attack Analysis</h2>

        <h3>Success Rate by Attack Type</h3>
        <div style="color:var(--muted); font-size:13px; margin-bottom:8px;">Based on unique prompts that succeeded in at least one attack of this type</div>
        <div class="plot-container">
          {charts['fig_attack_type_html']}
        </div>

        <h3>Success Rate by Attack Name</h3>
        <div class="plot-container">
          {charts['fig_attacks_html']}
        </div>

        <h3>📊 Detailed Attack Statistics</h3>
        {data_tables['attack_detailed_html']}
      </div>

      <!-- Content Analysis -->
      <div id="tab3" class="section" style="display:none;">
        <h2>📝 Content Analysis</h2>

        <h3>Response Length Distribution by Attack Success</h3>
        <div class="plot-container">
          {charts['fig_length_html']}
        </div>

        <h3>Average Response Length by Attack Type</h3>
        <div class="plot-container">
          {charts['fig_avg_length_html']}
        </div>

        <h3>Response Quality Analysis</h3>
        <div class="plot-container">
          {charts['fig_answer_html']}
        </div>
      </div>

      <!-- Data Explorer -->
      <div id="tab4" class="section" style="display:none;">
        <h2>🔍 Data Explorer</h2>
        {controls_html}
        <div style="margin-bottom:8px; color: var(--muted);"><span id="filtered-count"></span></div>
        {data_tables['explorer_table_html']}

        <h3 style="margin-top:16px;">Sample Prompts & Responses (up to 5)</h3>
        {data_tables['samples_html']}
      </div>

      <!-- Mitigations -->
      <div id="tab5" class="section" style="display:none;">
        <h2>🛡️ Mitigation Recommendations</h2>
        <div style="background:#1a1a10; border:1px solid #3a351b; padding:14px 18px; border-radius:10px; margin-bottom:16px; color:#ffd29b; font-size:14px;">
          The mitigations listed below are general recommendations based on detected attack categories. A professional security audit is needed to determine the concrete mitigations applicable to your specific use case and environment.
        </div>
        {mitigations_html}
      </div>

      <div class="footer">
        <hr/>
        <div>✅ Loaded {len(df)} records • <strong>Model:</strong> {metrics['model_name']} • <strong>Attack Types:</strong> {metrics['n_attack_types']} • <strong>Total Attacks:</strong> {metrics['n_attacks']}</div>
        <div><strong>Report Generated:</strong> {generated_at}</div>
      </div>
    </div>

    {controls_js}
    </body>
    </html>
    """

    return html

def main():
    parser = argparse.ArgumentParser(description="Generate static HTML report for framework results")
    parser.add_argument("--data-file", type=str, default="df.csv", help="Path to data file (default: df.csv)")
    parser.add_argument("--output", "-o", type=str, default="Static_report.html", help="Output HTML file path (default: Static_report.html)")
    args = parser.parse_args()

    try:
        df = load_data(args.data_file)
        if df.empty:
            print("Warning: No data loaded. Generating empty report.")

        metrics = calculate_metrics(df)
        charts = create_charts(df)
        data_tables = generate_data_tables(df)

        # Use the shared HTML builder
        html = build_html_report(df, metrics, charts, data_tables)

        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"Report generated: {args.output}")

    except Exception as e:
        print(f"Error processing data: {e}")
        import traceback
        traceback.print_exc()
        return


if __name__ == "__main__":
    main()