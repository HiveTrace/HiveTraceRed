# Fix the f-string issue by building the attribute string separately and re-writing the file.

import os, json, argparse
from datetime import datetime
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.io as pio
from hivetracered.pipeline.owasp_mapping import map_to_owasp, get_owasp_description

def get_chart_style():
    return {
        "paper_bgcolor": "#161a23",
        "plot_bgcolor": "#161a23",
        "font": dict(color="#e8e8e8"),
        "xaxis": dict(gridcolor="#2a2f3a", color="#e8e8e8"),
        "yaxis": dict(gridcolor="#2a2f3a", color="#e8e8e8")
    }

def load_data(file_path="df.parquet"):
    try:
        df = pd.read_parquet(file_path)
    except Exception as e:
        print(f"Error loading data: {e}")
        return pd.DataFrame()

    if "evaluation" in df.columns:
        def safe_get(d, key, default="unknown"):
            if isinstance(d, dict):
                return d.get(key, default)
            try:
                dd = json.loads(d)
                if isinstance(dd, dict):
                    return dd.get(key, default)
            except Exception:
                pass
            return default

        df["is_harmful"] = df["evaluation"].apply(lambda x: safe_get(x, "is_harmful"))
        df["did_answer"] = df["evaluation"].apply(lambda x: safe_get(x, "did_answer"))
        df["should_block"] = df["evaluation"].apply(lambda x: safe_get(x, "should_block"))

    for col in ["success", "is_blocked"]:
        if col in df.columns:
            df[col] = df[col].astype(bool)

    if "response" in df.columns:
        df["response_length"] = df["response"].fillna("").astype(str).str.len()

    return df

def calculate_metrics(df):
    total_tests = len(df) if len(df) else 0
    success_rate = float(df["success"].mean()*100) if "success" in df.columns and len(df) else 0.0
    blocked_rate = float(df["is_blocked"].mean()*100) if "is_blocked" in df.columns and len(df) else 0.0
    error_count = int(((df["error"].notna()) & (df["error"] != "")).sum()) if "error" in df.columns and len(df) else 0
    error_rate = float(error_count/len(df)*100) if len(df) else 0.0

    model_name = df["model"].iloc[0] if "model" in df.columns and len(df) else "Unknown"
    n_attack_types = df["attack_type"].nunique() if "attack_type" in df.columns else 0
    n_attacks = df["attack_name"].nunique() if "attack_name" in df.columns else 0

    best_attack_name = "-"
    best_attack_rate = 0.0
    vulnerable_prompts = 0
    total_prompts = 0
    vulnerable_prompts_rate = 0.0
    if "attack_name" in df.columns and "success" in df.columns and len(df):
        g = df.groupby("attack_name")["success"].agg(["count", "sum", "mean"]).reset_index()
        if len(g):
            idx = g["mean"].idxmax()
            best_attack_name = str(g.loc[idx, "attack_name"])
            best_attack_rate = float(g.loc[idx, "mean"] * 100)
    if "base_prompt" in df.columns and "success" in df.columns and len(df):
        vulnerable_prompts = int(df.loc[df["success"] == True, "base_prompt"].nunique())
        total_prompts = int(df["base_prompt"].nunique())
        vulnerable_prompts_rate = float(vulnerable_prompts / total_prompts * 100) if total_prompts > 0 else 0.0

    # OWASP Top 10 for LLM
    base_category = df["category"].iloc[0] if "category" in df.columns and len(df) else "Unknown"
    attack_names = df["attack_name"].unique().tolist() if "attack_name" in df.columns else []
    subcategories = df["subcategory"].unique().tolist() if "subcategory" in df.columns else None
    owasp_categories = sorted(map_to_owasp(base_category, attack_names, subcategories))

    # Calculate average ASR for NoneAttack
    asr_none_attack = 0.0
    if "attack_name" in df.columns and "success" in df.columns and len(df):
        none_attack_df = df[df["attack_name"] == "NoneAttack"]
        if len(none_attack_df) > 0:
            asr_none_attack = float(none_attack_df["success"].mean() * 100)

    # Calculate max of average ASR for each other attack (non-NoneAttack)
    asr_max_attack = 0.0
    best_attack_name_detailed = "-"
    if "attack_name" in df.columns and "success" in df.columns and len(df):
        injection_df = df[df["attack_name"] != "NoneAttack"]
        if len(injection_df) > 0:
            # Group by attack_name and get average ASR for each attack
            attack_stats = injection_df.groupby("attack_name")["success"].mean()
            if len(attack_stats) > 0:
                asr_max_attack = float(attack_stats.max() * 100)
                best_attack_name_detailed = str(attack_stats.idxmax())

    return {
        "total_tests": total_tests, "success_rate": success_rate, "blocked_rate": blocked_rate,
        "error_rate": error_rate, "model_name": model_name, "n_attack_types": n_attack_types,
        "n_attacks": n_attacks, "best_attack_name": best_attack_name, "best_attack_rate": best_attack_rate,
        "vulnerable_prompts": vulnerable_prompts, "total_prompts": total_prompts,
        "vulnerable_prompts_rate": vulnerable_prompts_rate,
        "base_category": base_category, "owasp_categories": owasp_categories,
        "asr_none_attack": asr_none_attack, "asr_max_attack": asr_max_attack,
        "best_attack_name_detailed": best_attack_name_detailed
    }

def create_charts(df):
    charts = {}

    fig_top_types_html = ""
    if {"attack_type","success","attack_name","base_prompt"}.issubset(df.columns):
        # Calculate success rate based on unique prompts
        # For each attack type, count unique prompts that succeeded in ANY attack of that type
        type_stats = []
        for attack_type in df["attack_type"].unique():
            type_df = df[df["attack_type"] == attack_type]
            # Get all unique prompts tested in this type
            total_unique_prompts = type_df["base_prompt"].nunique()
            # Get unique prompts that succeeded at least once in this type
            successful_prompts = type_df[type_df["success"] == True]["base_prompt"].nunique()
            # Calculate ASR
            success_rate = successful_prompts / total_unique_prompts if total_unique_prompts > 0 else 0.0
            type_stats.append({
                "attack_type": attack_type,
                "Success Rate": success_rate,
                "Total Unique Prompts": total_unique_prompts,
                "Successful Prompts": successful_prompts
            })
        top_types = pd.DataFrame(type_stats)
        top_types["Success Rate"] = top_types["Success Rate"] * 100
        top_types = top_types.sort_values("Success Rate", ascending=False).head(3).reset_index(drop=True)
        fig_top_types = px.bar(
            top_types, x="Success Rate", y="attack_type", orientation="h",
            text="Success Rate"
        )
        fig_top_types.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig_top_types.update_layout(
            xaxis_title="Success Rate (% of Unique Prompts)", yaxis_title="Attack Type", height=350, margin=dict(l=10,r=10,t=30,b=10),
            **get_chart_style()
        )
        fig_top_types_html = pio.to_html(fig_top_types, include_plotlyjs=True, full_html=False)

    fig_top_attacks_html = ""
    if {"attack_name","success"}.issubset(df.columns):
        top_attacks = (
            df.groupby("attack_name")["success"]
              .agg(["count","sum","mean"]).rename(columns={"count":"Total Tests","sum":"Successes","mean":"Success Rate"})
        )
        top_attacks["Success Rate"] = top_attacks["Success Rate"] * 100
        top_attacks = top_attacks.sort_values("Success Rate", ascending=False).head(3).reset_index()
        fig_top_attacks = px.bar(
            top_attacks, x="Success Rate", y="attack_name", orientation="h",
            text="Success Rate"
        )
        fig_top_attacks.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig_top_attacks.update_layout(
            xaxis_title="Success Rate (%)", yaxis_title="Attack Name", height=350, margin=dict(l=10,r=10,t=30,b=10),
            **get_chart_style()
        )
        if fig_top_types_html:
            fig_top_attacks_html = pio.to_html(fig_top_attacks, include_plotlyjs=False, full_html=False)
        else:
            fig_top_attacks_html = pio.to_html(fig_top_attacks, include_plotlyjs=True, full_html=False)

    fig_attack_type_html = ""
    if {"attack_type","success","is_blocked","attack_name","base_prompt"}.issubset(df.columns):
        # Calculate success rate based on unique prompts
        # For each attack type, count unique prompts that succeeded in ANY attack of that type
        type_stats = []
        for attack_type in df["attack_type"].unique():
            type_df = df[df["attack_type"] == attack_type]
            # Get all unique prompts tested in this type
            total_unique_prompts = type_df["base_prompt"].nunique()
            # Get unique prompts that succeeded at least once in this type
            successful_prompts = type_df[type_df["success"] == True]["base_prompt"].nunique()
            # Calculate ASR
            success_rate = successful_prompts / total_unique_prompts if total_unique_prompts > 0 else 0.0
            # Get block rate
            block_rate = type_df["is_blocked"].mean()
            type_stats.append({
                "attack_type": attack_type,
                "Success Rate": success_rate * 100,
                "Total Unique Prompts": total_unique_prompts,
                "Successful Prompts": successful_prompts,
                "Block Rate": block_rate * 100
            })
        attack_type_stats = pd.DataFrame(type_stats)

        attack_type_stats = attack_type_stats[attack_type_stats["Success Rate"] > 3]

        if len(attack_type_stats) > 0:
            fig_attack_type = px.bar(attack_type_stats, x="attack_type", y="Success Rate")
            fig_attack_type.update_layout(
                xaxis_title="Attack Type", yaxis_title="Success Rate (% of Unique Prompts)", height=400, margin=dict(l=10,r=10,t=30,b=10),
                **get_chart_style()
            )
            fig_attack_type_html = pio.to_html(fig_attack_type, include_plotlyjs=False, full_html=False)
        else:
            fig_attack_type_html = "<p style='color: var(--muted); text-align: center; padding: 40px;'>No attack types with success rate > 3%</p>"

    fig_attacks_html = ""
    if {"attack_name","success","is_blocked"}.issubset(df.columns):
        attack_stats = (
            df.groupby("attack_name")
            .agg({"success":["count","sum","mean"], "is_blocked":"mean"})
        )
        attack_stats.columns = ["Total Tests","Successes","Success Rate","Block Rate"]
        attack_stats["Success Rate"] = attack_stats["Success Rate"] * 100
        attack_stats["Block Rate"] = attack_stats["Block Rate"] * 100
        attack_stats = attack_stats.reset_index()

        attack_stats = attack_stats[attack_stats["Success Rate"] > 3]

        if len(attack_stats) > 0:
            fig_attacks = px.bar(attack_stats, x="attack_name", y="Success Rate")
            fig_attacks.update_layout(
                xaxis_title="Attack Name", yaxis_title="Success Rate (%)", xaxis_tickangle=45, height=500, margin=dict(l=10,r=10,t=30,b=50),
                **get_chart_style()
            )
            fig_attacks_html = pio.to_html(fig_attacks, include_plotlyjs=False, full_html=False)
        else:
            fig_attacks_html = "<p style='color: var(--muted); text-align: center; padding: 40px;'>No individual attacks with success rate > 3%</p>"

    fig_length_html = ""
    fig_avg_length_html = ""
    if {"response_length","success","attack_type"}.issubset(df.columns):
        fig_length = px.box(df, x="success", y="response_length", color="success")
        fig_length.update_layout(
            xaxis_title="Attack Success", yaxis_title="Response Length (chars)", height=400, margin=dict(l=10,r=10,t=30,b=10),
            **get_chart_style()
        )
        fig_length_html = pio.to_html(fig_length, include_plotlyjs=False, full_html=False)

        avg_length = df.groupby("attack_type")["response_length"].mean().reset_index()
        fig_avg_length = px.bar(avg_length, x="attack_type", y="response_length")
        fig_avg_length.update_layout(
            xaxis_title="Attack Type", yaxis_title="Avg Response Length (chars)", xaxis_tickangle=45, height=400, margin=dict(l=10,r=10,t=30,b=50),
            **get_chart_style()
        )
        fig_avg_length_html = pio.to_html(fig_avg_length, include_plotlyjs=False, full_html=False)

    fig_answer_html = ""
    if {"did_answer","success"}.issubset(df.columns) and len(df):
        answer_analysis = pd.crosstab(df["did_answer"], df["success"], normalize="index") * 100
        answer_long = answer_analysis.reset_index().melt(id_vars="did_answer", var_name="success", value_name="pct")
        fig_answer = px.bar(answer_long, x="did_answer", y="pct", color="success", barmode="stack")
        fig_answer.update_layout(
            xaxis_title="Did Answer", yaxis_title="Percentage", height=400, margin=dict(l=10,r=10,t=30,b=10),
            **get_chart_style()
        )
        fig_answer_html = pio.to_html(fig_answer, include_plotlyjs=False, full_html=False)

    return {
        "fig_top_types_html": fig_top_types_html,
        "fig_top_attacks_html": fig_top_attacks_html,
        "fig_attack_type_html": fig_attack_type_html,
        "fig_attacks_html": fig_attacks_html,
        "fig_length_html": fig_length_html,
        "fig_avg_length_html": fig_avg_length_html,
        "fig_answer_html": fig_answer_html
    }

def generate_data_tables(df):
    attack_detailed_html = ""
    if {"attack_type","attack_name","success","is_blocked"}.issubset(df.columns):
        attack_detailed = (
            df.groupby(["attack_type","attack_name"])
            .agg({
                "success":["count","sum","mean"],
                "is_blocked":"mean",
                "error": lambda x: (x.notna() & (x != "")).sum() if "error" in df.columns else 0
            })
        )
        attack_detailed.columns = ["Total Tests","Successes","Success Rate","Block Rate","Errors"]
        attack_detailed["Success Rate"] = attack_detailed["Success Rate"] * 100
        attack_detailed["Block Rate"] = attack_detailed["Block Rate"] * 100
        attack_detailed = attack_detailed.reset_index()
        attack_detailed["Success Rate"] = attack_detailed["Success Rate"].round(1).astype(str) + "%"
        attack_detailed["Block Rate"] = attack_detailed["Block Rate"].round(1).astype(str) + "%"
        attack_detailed_html = attack_detailed.to_html(index=False, classes="dataframe compact", border=0)

    display_columns = [c for c in ["attack_name","attack_type","success","is_blocked"] if c in df.columns]
    explorer_table_rows = []
    if display_columns:
        for _, r in df[display_columns].fillna("").iterrows():
            def bfmt(x):
                if isinstance(x, (bool, np.bool_)):
                    return "✅" if x else "❌"
                return str(x)
            attrs = {
                "data-attack-type": str(r.get("attack_type","")),
                "data-success": str(r.get("success","")).lower(),
                "data-blocked": str(r.get("is_blocked","")).lower()
            }
            attrs_str = " ".join([f'{k}="{v}"' for k, v in attrs.items()])
            tds = "".join(f"<td>{bfmt(r[c])}</td>" for c in display_columns)
            explorer_table_rows.append(f"<tr {attrs_str}>{tds}</tr>")
    explorer_table_html = f"""
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

    samples_html = ""
    if {"attack_name","success","base_prompt","prompt","response"}.issubset(df.columns) and len(df):
        sample_pool = df[df["success"] == True]
        if len(sample_pool) == 0:
            sample_pool = df
        sample_df = sample_pool.sample(min(5, len(sample_pool)), random_state=7)
        blocks = []
        for _, row in sample_df.iterrows():
            title = f"{row.get('attack_name','Unknown')} - {'✅ Success' if bool(row.get('success', False)) else '❌ Failed'}"
            bp = str(row.get("base_prompt","N/A"))
            pr = str(row.get("prompt","N/A"))
            rs = str(row.get("response","N/A"))
            def trim(s, n=800):
                return (s[:n] + "…") if len(s) > n else s
            blocks.append(f"""
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
    """)
        samples_html = "\n".join(blocks)

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

    # Build OWASP categories HTML
    owasp_badges_html = ""
    if metrics.get('owasp_categories'):
        owasp_badges = []
        for cat in metrics['owasp_categories']:
            owasp_badges.append(f'<div class="badge" style="background:#1a1e3a; border-color:#2a3a5a; color:#9bb4e3;" title="{get_owasp_description(cat)}">{cat}</div>')
        owasp_badges_html = "\n          ".join(owasp_badges)

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

        <h3>📊 OWASP Top 10 for LLM</h3>
        <div style="background:#0f1420; border:1px solid var(--border); padding:16px; border-radius:12px; margin-bottom:16px;">
          <div style="margin-bottom:12px;"><strong>Category:</strong> <span style="color:var(--accent2);">{metrics.get('base_category', 'Unknown')}</span></div>
          <div style="margin-bottom:8px;"><strong>OWASP Categories:</strong></div>
          <div class="kf">
            {owasp_badges_html if owasp_badges_html else '<div style="color:var(--muted);">No OWASP categories mapped</div>'}
          </div>
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
    parser.add_argument("--data-file", type=str, default="df.parquet", help="Path to data file (default: df.parquet)")
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