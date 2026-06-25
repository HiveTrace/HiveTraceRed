import argparse
import json
import os
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.io as pio
from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup

from hivetracered.pipeline.framework_mapping import (
    FRAMEWORKS,
    get_framework_mappings,
)
from hivetracered.pipeline.mitigations import get_prioritized_mitigations

_JINJA_ENV = Environment(
    loader=PackageLoader("hivetracered", "templates"),
    autoescape=select_autoescape(["html", "xml"]),
)


CHART_COLORS = ["#2563eb", "#60a5fa", "#3b82f6", "#93c5fd", "#1d4ed8"]


def get_chart_style():
    return {
        "paper_bgcolor": "#09090b",
        "plot_bgcolor": "#09090b",
        "font": dict(color="#fafafa"),
        "xaxis": dict(gridcolor="#27272a", color="#a1a1aa"),
        "yaxis": dict(gridcolor="#27272a", color="#a1a1aa"),
        "colorway": CHART_COLORS,
    }


def load_data(file_path="df.csv"):
    try:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".parquet":
            df = pd.read_parquet(file_path)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path)
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
    success_rate = float(df["success"].mean() * 100) if "success" in df.columns and len(df) else 0.0
    blocked_rate = float(df["is_blocked"].mean() * 100) if "is_blocked" in df.columns and len(df) else 0.0
    error_count = (
        int(((df["error"].notna()) & (df["error"] != "")).sum())
        if "error" in df.columns and len(df)
        else 0
    )
    error_rate = float(error_count / len(df) * 100) if len(df) else 0.0

    model_name = df["model"].iloc[0] if "model" in df.columns and len(df) else "Unknown"
    n_attack_types = df["attack_type"].nunique() if "attack_type" in df.columns else 0
    n_attacks = df["attack_name"].nunique() if "attack_name" in df.columns else 0

    best_attack_name = "-"
    best_attack_rate = 0.0
    vulnerable_prompts = 0
    total_prompts = 0
    vulnerable_prompts_rate = 0.0

    if "attack_name" in df.columns and "success" in df.columns and len(df):
        grouped = df.groupby("attack_name")["success"].agg(["count", "sum", "mean"]).reset_index()
        if len(grouped):
            idx = grouped["mean"].idxmax()
            best_attack_name = str(grouped.loc[idx, "attack_name"])
            best_attack_rate = float(grouped.loc[idx, "mean"] * 100)

    if "base_prompt" in df.columns and "success" in df.columns and len(df):
        vulnerable_prompts = int(df.loc[df["success"] == True, "base_prompt"].nunique())
        total_prompts = int(df["base_prompt"].nunique())
        vulnerable_prompts_rate = (
            float(vulnerable_prompts / total_prompts * 100) if total_prompts > 0 else 0.0
        )

    base_category = df["category"].iloc[0] if "category" in df.columns and len(df) else "Unknown"
    subcategories = df["subcategory"].unique().tolist() if "subcategory" in df.columns else None

    merged_mappings: dict = {}
    if "attack_type" in df.columns and "attack_name" in df.columns and len(df):
        pairs = df[["attack_type", "attack_name"]].drop_duplicates()
        for _, row in pairs.iterrows():
            mapping = get_framework_mappings(
                attack_type=row["attack_type"],
                attack_name=row["attack_name"],
                base_category=base_category,
                subcategories=subcategories,
            )
            for framework, categories in mapping.items():
                merged_mappings.setdefault(framework, set()).update(categories)
    else:
        merged_mappings = get_framework_mappings(
            base_category=base_category, subcategories=subcategories
        )

    framework_categories: dict = {}
    for framework, category_ids in merged_mappings.items():
        fw_defs = FRAMEWORKS.get(framework, {}).get("categories", {})
        framework_categories[framework] = sorted(
            f"{cid}: {fw_defs[cid]['name']}" for cid in category_ids if cid in fw_defs
        )

    asr_none_attack = 0.0
    if "attack_name" in df.columns and "success" in df.columns and len(df):
        none_attack_df = df[df["attack_name"] == "NoneAttack"]
        if len(none_attack_df) > 0:
            asr_none_attack = float(none_attack_df["success"].mean() * 100)

    asr_max_attack = 0.0
    best_attack_name_detailed = "-"
    if "attack_name" in df.columns and "success" in df.columns and len(df):
        injection_df = df[df["attack_name"] != "NoneAttack"]
        if len(injection_df) > 0:
            attack_stats = injection_df.groupby("attack_name")["success"].mean()
            if len(attack_stats) > 0:
                asr_max_attack = float(attack_stats.max() * 100)
                best_attack_name_detailed = str(attack_stats.idxmax())

    vulnerable_attack_types = []
    if "attack_type" in df.columns and "success" in df.columns and len(df):
        type_asr = df.groupby("attack_type")["success"].mean()
        vulnerable_attack_types = sorted(type_asr[type_asr > 0].index.tolist())

    prioritized_mitigations = get_prioritized_mitigations(vulnerable_attack_types)

    return {
        "total_tests": total_tests,
        "success_rate": success_rate,
        "blocked_rate": blocked_rate,
        "error_rate": error_rate,
        "model_name": model_name,
        "n_attack_types": n_attack_types,
        "n_attacks": n_attacks,
        "best_attack_name": best_attack_name,
        "best_attack_rate": best_attack_rate,
        "vulnerable_prompts": vulnerable_prompts,
        "total_prompts": total_prompts,
        "vulnerable_prompts_rate": vulnerable_prompts_rate,
        "base_category": base_category,
        "framework_categories": framework_categories,
        "framework_mappings": {k: sorted(v) for k, v in merged_mappings.items()},
        "asr_none_attack": asr_none_attack,
        "asr_max_attack": asr_max_attack,
        "best_attack_name_detailed": best_attack_name_detailed,
        "vulnerable_attack_types": vulnerable_attack_types,
        "prioritized_mitigations": prioritized_mitigations,
    }


def create_charts(df):
    fig_top_types_html = ""
    if {"attack_type", "success", "attack_name", "base_prompt"}.issubset(df.columns):
        type_stats = []
        for attack_type in df["attack_type"].unique():
            type_df = df[df["attack_type"] == attack_type]
            total_unique_prompts = type_df["base_prompt"].nunique()
            successful_prompts = type_df[type_df["success"] == True]["base_prompt"].nunique()
            success_rate = successful_prompts / total_unique_prompts if total_unique_prompts > 0 else 0.0
            type_stats.append(
                {
                    "attack_type": attack_type,
                    "Success Rate": success_rate,
                    "Total Unique Prompts": total_unique_prompts,
                    "Successful Prompts": successful_prompts,
                }
            )
        top_types = pd.DataFrame(type_stats)
        top_types["Success Rate"] = top_types["Success Rate"] * 100
        top_types = top_types.sort_values("Success Rate", ascending=False).head(3).reset_index(drop=True)
        fig_top_types = px.bar(top_types, x="Success Rate", y="attack_type", orientation="h", text="Success Rate")
        fig_top_types.update_traces(texttemplate="%{text:.1f}%", textposition="outside", marker_color=CHART_COLORS[0])
        fig_top_types.update_layout(
            xaxis_title="Success Rate (% of Unique Prompts)",
            yaxis_title="Attack Type",
            height=350,
            margin=dict(l=10, r=10, t=30, b=10),
            **get_chart_style(),
        )
        fig_top_types_html = pio.to_html(fig_top_types, include_plotlyjs=True, full_html=False)

    fig_top_attacks_html = ""
    if {"attack_name", "success"}.issubset(df.columns):
        top_attacks = (
            df.groupby("attack_name")["success"]
            .agg(["count", "sum", "mean"])
            .rename(columns={"count": "Total Tests", "sum": "Successes", "mean": "Success Rate"})
        )
        top_attacks["Success Rate"] = top_attacks["Success Rate"] * 100
        top_attacks = top_attacks.sort_values("Success Rate", ascending=False).head(3).reset_index()
        fig_top_attacks = px.bar(top_attacks, x="Success Rate", y="attack_name", orientation="h", text="Success Rate")
        fig_top_attacks.update_traces(texttemplate="%{text:.1f}%", textposition="outside", marker_color=CHART_COLORS[0])
        fig_top_attacks.update_layout(
            xaxis_title="Success Rate (%)",
            yaxis_title="Attack Name",
            height=350,
            margin=dict(l=10, r=10, t=30, b=10),
            **get_chart_style(),
        )
        fig_top_attacks_html = pio.to_html(
            fig_top_attacks,
            include_plotlyjs=not bool(fig_top_types_html),
            full_html=False,
        )

    fig_attack_type_html = ""
    if {"attack_type", "success", "is_blocked", "attack_name", "base_prompt"}.issubset(df.columns):
        type_stats = []
        for attack_type in df["attack_type"].unique():
            type_df = df[df["attack_type"] == attack_type]
            total_unique_prompts = type_df["base_prompt"].nunique()
            successful_prompts = type_df[type_df["success"] == True]["base_prompt"].nunique()
            success_rate = successful_prompts / total_unique_prompts if total_unique_prompts > 0 else 0.0
            block_rate = type_df["is_blocked"].mean()
            type_stats.append(
                {
                    "attack_type": attack_type,
                    "Success Rate": success_rate * 100,
                    "Total Unique Prompts": total_unique_prompts,
                    "Successful Prompts": successful_prompts,
                    "Block Rate": block_rate * 100,
                }
            )
        attack_type_stats = pd.DataFrame(type_stats)
        attack_type_stats = attack_type_stats[attack_type_stats["Success Rate"] > 3]

        if len(attack_type_stats) > 0:
            fig_attack_type = px.bar(attack_type_stats, x="attack_type", y="Success Rate")
            fig_attack_type.update_traces(marker_color=CHART_COLORS[0])
            fig_attack_type.update_layout(
                xaxis_title="Attack Type",
                yaxis_title="Success Rate (% of Unique Prompts)",
                height=400,
                margin=dict(l=10, r=10, t=30, b=10),
                **get_chart_style(),
            )
            fig_attack_type_html = pio.to_html(fig_attack_type, include_plotlyjs=False, full_html=False)
        else:
            fig_attack_type_html = (
                "<p style='color: var(--muted); text-align: center; padding: 40px;'>"
                "No attack types with success rate > 3%</p>"
            )

    fig_attacks_html = ""
    if {"attack_name", "success", "is_blocked"}.issubset(df.columns):
        attack_stats = df.groupby("attack_name").agg({"success": ["count", "sum", "mean"], "is_blocked": "mean"})
        attack_stats.columns = ["Total Tests", "Successes", "Success Rate", "Block Rate"]
        attack_stats["Success Rate"] = attack_stats["Success Rate"] * 100
        attack_stats["Block Rate"] = attack_stats["Block Rate"] * 100
        attack_stats = attack_stats.reset_index()
        attack_stats = attack_stats[attack_stats["Success Rate"] > 3]

        if len(attack_stats) > 0:
            fig_attacks = px.bar(attack_stats, x="attack_name", y="Success Rate")
            fig_attacks.update_traces(marker_color=CHART_COLORS[0])
            fig_attacks.update_layout(
                xaxis_title="Attack Name",
                yaxis_title="Success Rate (%)",
                xaxis_tickangle=45,
                height=500,
                margin=dict(l=10, r=10, t=30, b=50),
                **get_chart_style(),
            )
            fig_attacks_html = pio.to_html(fig_attacks, include_plotlyjs=False, full_html=False)
        else:
            fig_attacks_html = (
                "<p style='color: var(--muted); text-align: center; padding: 40px;'>"
                "No individual attacks with success rate > 3%</p>"
            )

    fig_length_html = ""
    fig_avg_length_html = ""
    if {"response_length", "success", "attack_type"}.issubset(df.columns):
        fig_length = px.box(df, x="success", y="response_length", color="success", color_discrete_sequence=CHART_COLORS)
        fig_length.update_layout(
            xaxis_title="Attack Success",
            yaxis_title="Response Length (chars)",
            height=400,
            margin=dict(l=10, r=10, t=30, b=10),
            **get_chart_style(),
        )
        fig_length_html = pio.to_html(fig_length, include_plotlyjs=False, full_html=False)

        avg_length = df.groupby("attack_type")["response_length"].mean().reset_index()
        fig_avg_length = px.bar(avg_length, x="attack_type", y="response_length")
        fig_avg_length.update_traces(marker_color=CHART_COLORS[0])
        fig_avg_length.update_layout(
            xaxis_title="Attack Type",
            yaxis_title="Avg Response Length (chars)",
            xaxis_tickangle=45,
            height=400,
            margin=dict(l=10, r=10, t=30, b=50),
            **get_chart_style(),
        )
        fig_avg_length_html = pio.to_html(fig_avg_length, include_plotlyjs=False, full_html=False)

    fig_answer_html = ""
    if {"did_answer", "success"}.issubset(df.columns) and len(df):
        answer_analysis = pd.crosstab(df["did_answer"], df["success"], normalize="index") * 100
        answer_long = answer_analysis.reset_index().melt(id_vars="did_answer", var_name="success", value_name="pct")
        fig_answer = px.bar(answer_long, x="did_answer", y="pct", color="success", barmode="stack", color_discrete_sequence=CHART_COLORS)
        fig_answer.update_layout(
            xaxis_title="Did Answer",
            yaxis_title="Percentage",
            height=400,
            margin=dict(l=10, r=10, t=30, b=10),
            **get_chart_style(),
        )
        fig_answer_html = pio.to_html(fig_answer, include_plotlyjs=False, full_html=False)

    return {
        "fig_top_types_html": fig_top_types_html,
        "fig_top_attacks_html": fig_top_attacks_html,
        "fig_attack_type_html": fig_attack_type_html,
        "fig_attacks_html": fig_attacks_html,
        "fig_length_html": fig_length_html,
        "fig_avg_length_html": fig_avg_length_html,
        "fig_answer_html": fig_answer_html,
    }


def generate_data_tables(df):
    attack_detailed_html = ""
    if {"attack_type", "attack_name", "success", "is_blocked"}.issubset(df.columns):
        agg_spec = {
            "success": ["count", "sum", "mean"],
            "is_blocked": "mean",
        }
        has_error_col = "error" in df.columns
        if has_error_col:
            agg_spec["error"] = lambda x: (x.notna() & (x != "")).sum()

        attack_detailed = df.groupby(["attack_type", "attack_name"]).agg(agg_spec)
        if has_error_col:
            attack_detailed.columns = ["Total Tests", "Successes", "Success Rate", "Block Rate", "Errors"]
        else:
            attack_detailed.columns = ["Total Tests", "Successes", "Success Rate", "Block Rate"]
            attack_detailed["Errors"] = 0
        attack_detailed["Success Rate"] = attack_detailed["Success Rate"] * 100
        attack_detailed["Block Rate"] = attack_detailed["Block Rate"] * 100
        attack_detailed = attack_detailed.reset_index()
        attack_detailed["Success Rate"] = attack_detailed["Success Rate"].round(1).astype(str) + "%"
        attack_detailed["Block Rate"] = attack_detailed["Block Rate"].round(1).astype(str) + "%"
        attack_detailed_html = attack_detailed.to_html(index=False, classes="dataframe compact", border=0)

    display_columns = [c for c in ["attack_name", "attack_type", "success", "is_blocked"] if c in df.columns]
    explorer_table_rows = []
    if display_columns:
        for _, row in df[display_columns].fillna("").iterrows():
            def bfmt(x):
                if isinstance(x, (bool, np.bool_)):
                    return "✅" if x else "❌"
                return str(x)

            attrs = {
                "data-attack-type": str(row.get("attack_type", "")),
                "data-success": str(row.get("success", "")).lower(),
                "data-blocked": str(row.get("is_blocked", "")).lower(),
            }
            attrs_str = " ".join([f'{k}="{v}"' for k, v in attrs.items()])
            tds = "".join(f"<td>{bfmt(row[c])}</td>" for c in display_columns)
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
    if {"attack_name", "success", "base_prompt", "prompt", "response"}.issubset(df.columns) and len(df):
        sample_pool = df[df["success"] == True]
        if len(sample_pool) == 0:
            sample_pool = df
        sample_df = sample_pool.sample(min(5, len(sample_pool)), random_state=7)
        blocks = []
        for _, row in sample_df.iterrows():
            title = (
                f"{row.get('attack_name','Unknown')} - "
                f"{'✅ Success' if bool(row.get('success', False)) else '❌ Failed'}"
            )
            bp = str(row.get("base_prompt", "N/A"))
            prompt = str(row.get("prompt", "N/A"))
            response = str(row.get("response", "N/A"))
            blocks.append(
                f"""
    <details class="sample-block">
      <summary>{title}</summary>
      <div class="sample-inner">
        <h4>Base Prompt</h4>
        <pre>{bp}</pre>
        <h4>Attack Prompt</h4>
        <pre>{prompt}</pre>
        <h4>Model Response</h4>
        <pre>{response}</pre>
      </div>
    </details>
    """
            )
        samples_html = "\n".join(blocks)

    return {
        "attack_detailed_html": attack_detailed_html,
        "explorer_table_html": explorer_table_html,
        "samples_html": samples_html,
    }


def _build_framework_groups(metrics):
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

    groups = []
    framework_categories = metrics.get("framework_categories", {})
    for fw_key in ["OWASP_LLM_TOP_10", "MITRE_ATLAS", "FSTEK_117"]:
        categories = framework_categories.get(fw_key, [])
        if not categories:
            continue

        fw_name = fw_short.get(fw_key, fw_key)
        color, bg, border = fw_badge_colors.get(fw_key, ("#e8e8e8", "#1a1e3a", "#2a3a5a"))
        fw_defs = FRAMEWORKS.get(fw_key, {}).get("categories", {})

        badges = []
        for category in categories:
            cat_id = category.split(":")[0].strip()
            desc = fw_defs.get(cat_id, {}).get("description", "")
            badges.append(
                {
                    "text": category,
                    "desc": desc,
                    "style": f"background:{bg}; border-color:{border}; color:{color};",
                }
            )
        groups.append({"name": fw_name, "badges": badges})

    return groups


def _severity_from_rate(rate):
    if rate >= 0.5:
        return "critical"
    if rate >= 0.25:
        return "high"
    if rate >= 0.1:
        return "medium"
    return "low"


def _framework_id(value):
    return str(value).split(":", 1)[0].strip() if value else "-"


def _build_v2_report_context(df, metrics):
    success_col = df["success"].astype(bool) if "success" in df.columns and len(df) else pd.Series([], dtype=bool)
    error_col = (
        (df["error"].notna()) & (df["error"] != "")
        if "error" in df.columns and len(df)
        else pd.Series([False] * len(df))
    )
    failed_count = int(success_col.sum()) if len(df) else 0
    error_count = int(error_col.sum()) if len(df) else 0
    passed_count = max(int(len(df) - failed_count - error_count), 0)

    model_name = metrics.get("model_name", "Unknown")
    base_category = metrics.get("base_category", "Unknown")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    scan = {
        "scan_id": f"htr-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "scan_timestamp": now,
        "target_model": model_name,
        "target_label": model_name,
        "target_description": f"HiveTraceRed red team report for {base_category}",
        "attack_provider": "-",
        "grader_model": "Evaluator",
        "execution_time": "-",
        "tool_version": "HiveTraceRed",
        "token_usage": {"prompt": 0, "completion": 0, "cost": "-"},
        "config": json.dumps(
            {
                "data_records": len(df),
                "category": base_category,
                "attack_types": metrics.get("n_attack_types", 0),
                "attacks": metrics.get("n_attacks", 0),
            },
            indent=2,
            ensure_ascii=False,
        ),
    }
    summary = {
        "risk": float(metrics.get("success_rate", 0.0)),
        "total": int(len(df)),
        "passed": passed_count,
        "failed": failed_count,
        "errors": error_count,
    }

    owasp_ids = set(metrics.get("framework_mappings", {}).get("OWASP_LLM_TOP_10", []))
    mitre_ids = set(metrics.get("framework_mappings", {}).get("MITRE_ATLAS", []))
    owasp = sorted(owasp_ids)[0] if owasp_ids else "-"
    mitre_id = sorted(mitre_ids)[0] if mitre_ids else "-"

    cats = []
    if {"attack_type", "success"}.issubset(df.columns):
        for attack_type, group in df.groupby("attack_type"):
            total = len(group)
            failures = int(group["success"].astype(bool).sum())
            passes = max(total - failures, 0)
            rate = failures / total if total else 0.0
            cats.append(
                {
                    "cat": str(attack_type),
                    "plugin": str(attack_type),
                    "owasp": owasp,
                    "mitre": mitre_id,
                    "sev": _severity_from_rate(rate),
                    "p": passes,
                    "f": failures,
                }
            )
    cats.sort(key=lambda item: item["f"], reverse=True)

    strats = []
    if {"attack_name", "success"}.issubset(df.columns):
        for attack_name, group in df.groupby("attack_name"):
            strats.append(
                {
                    "name": str(attack_name),
                    "att": int(len(group)),
                    "succ": int(group["success"].astype(bool).sum()),
                }
            )
    strats.sort(key=lambda item: (item["succ"] / item["att"]) if item["att"] else 0.0, reverse=True)

    heat = {"cols": [], "rows": []}
    if {"attack_name", "attack_type", "success"}.issubset(df.columns):
        cols = sorted(str(v) for v in df["attack_type"].dropna().unique().tolist())
        heat_rows = []
        for attack_name in [s["name"] for s in strats[:10]]:
            values = []
            attack_df = df[df["attack_name"] == attack_name]
            for attack_type in cols:
                cell = attack_df[attack_df["attack_type"] == attack_type]
                values.append(float(cell["success"].astype(bool).mean()) if len(cell) else 0.0)
            heat_rows.append({"s": attack_name, "v": values})
        heat = {"cols": cols, "rows": heat_rows}

    owasp_defs = FRAMEWORKS.get("OWASP_LLM_TOP_10", {}).get("categories", {})
    owasp_data = []
    for category_id, definition in owasp_defs.items():
        mapped = category_id in owasp_ids
        owasp_data.append(
            {
                "id": category_id,
                "name": definition.get("name", category_id),
                "st": "fail" if mapped and failed_count else ("warn" if mapped else "skip"),
                "f": failed_count if mapped else 0,
                "cov": 100 if mapped else 0,
            }
        )

    mitre_defs = FRAMEWORKS.get("MITRE_ATLAS", {}).get("categories", {})
    mitre = []
    for category_id in sorted(mitre_ids):
        definition = mitre_defs.get(category_id, {})
        mitre.append(
            {
                "tactic": f"{category_id}: {definition.get('name', category_id)}",
                "tech": [category_id],
                "f": failed_count,
            }
        )

    findings = []
    if len(df) and "success" in df.columns:
        successful = df[df["success"].astype(bool)].head(100)
        type_rates = (
            df.groupby("attack_type")["success"].mean().to_dict()
            if {"attack_type", "success"}.issubset(df.columns)
            else {}
        )
        for idx, row in successful.iterrows():
            attack_type = str(row.get("attack_type", "Unknown"))
            attack_name = str(row.get("attack_name", "-"))
            rate = float(type_rates.get(attack_type, 0.0))
            evaluation = row.get("evaluation", "")
            findings.append(
                {
                    "id": f"F-{len(findings) + 1:03d}",
                    "type": attack_type,
                    "sub": attack_name,
                    "plugin": attack_name,
                    "detector": "evaluation.success",
                    "status": "failed",
                    "complexity": "single-turn",
                    "turns": 1,
                    "lang": "en",
                    "modality": "text",
                    "attempts": 1,
                    "hits": 1,
                    "risk": round(rate * 10, 1),
                    "conf": 1.0,
                    "sev": _severity_from_rate(rate),
                    "owasp": owasp,
                    "mitreTactic": mitre_id,
                    "mitreTech": mitre_id,
                    "strategy": attack_name,
                    "prompt": str(row.get("prompt", "")),
                    "response": str(row.get("response", "")),
                    "graderReasoning": str(evaluation) if evaluation else "Marked successful by evaluator.",
                    "remediation": "Review this attack path and harden system prompts, policy checks, and output validation for the affected category.",
                    "promptDiff": f"- vulnerable path: {attack_type} / {attack_name}\n+ add targeted policy checks and regression tests",
                }
            )

    return {
        "scan": scan,
        "summary": summary,
        "cats": cats,
        "strats": strats,
        "heat": heat,
        "owasp_data": owasp_data,
        "mitre": mitre,
        "trend": [],
        "findings": findings,
    }


def build_html_report(df, metrics, charts, data_tables):
    template = _JINJA_ENV.get_template("report/report_template.jinja")
    return template.render(**_build_v2_report_context(df, metrics))


def main():
    parser = argparse.ArgumentParser(description="Generate static HTML report for framework results")
    parser.add_argument("--data-file", type=str, default="df.csv", help="Path to data file (default: df.csv)")
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="Static_report.html",
        help="Output HTML file path (default: Static_report.html)",
    )
    args = parser.parse_args()

    try:
        df = load_data(args.data_file)
        if df.empty:
            print("Warning: No data loaded. Generating empty report.")

        metrics = calculate_metrics(df)
        charts = create_charts(df)
        data_tables = generate_data_tables(df)
        html = build_html_report(df, metrics, charts, data_tables)

        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"Report generated: {args.output}")
    except Exception as e:
        print(f"Error processing data: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
