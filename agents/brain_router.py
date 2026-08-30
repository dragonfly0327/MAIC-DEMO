import os
import sys
import re
import time
import json
import urllib.request
import urllib.parse
import configparser

# ──────────────────────────────────────────────
# Chart Generation Engine
# ──────────────────────────────────────────────
CHART_COLORS = [
    "#2b6cb0", "#2f855a", "#c05621", "#6b46c1",
    "#2c7a7b", "#b7791f", "#c53030", "#285e61",
    "#553c9a", "#276749"
]

def generate_rfq_chart(chart_type="stage", stats=None):
    """
    Generates a matplotlib Figure for embedding in Tkinter chat.
    chart_type: 'stage' | 'customer' | 'assembly' | 'overview'
    Returns: matplotlib.figure.Figure or None
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.figure import Figure
    except ImportError:
        return None

    if stats is None:
        stats = get_rfq_summary_stats()

    fig = Figure(figsize=(4.2, 2.8), dpi=96, facecolor="#f8fafc")
    ax = fig.add_subplot(111)
    ax.set_facecolor("#f8fafc")
    for spine in ax.spines.values():
        spine.set_edgecolor("#e2e8f0")

    if chart_type == "stage":
        stage_counts = stats.get("stage_counts", {})
        if not stage_counts:
            return None
        labels = [k.replace("_", " ").title() for k in stage_counts.keys()]
        values = list(stage_counts.values())
        colors = CHART_COLORS[:len(labels)]
        wedges, texts, autotexts = ax.pie(
            values, labels=None, autopct="%1.0f%%",
            colors=colors, startangle=140,
            wedgeprops=dict(linewidth=1.5, edgecolor="white"),
            pctdistance=0.78
        )
        for at in autotexts:
            at.set_fontsize(8)
            at.set_color("white")
            at.set_fontweight("bold")
        ax.legend(wedges, labels, loc="lower center", ncol=2,
                  bbox_to_anchor=(0.5, -0.18), fontsize=7, frameon=False)
        ax.set_title(f"RFQ Stage Distribution  (Total: {sum(values)})",
                     fontsize=9, fontweight="bold", color="#2d3748", pad=8)
        fig.tight_layout(rect=[0, 0.1, 1, 1])

    elif chart_type == "customer":
        cust_counts = stats.get("customer_counts", {})
        if not cust_counts:
            return None
        sorted_custs = sorted(cust_counts.items(), key=lambda x: x[1], reverse=True)[:8]
        labels = [c[0][:18] for c in sorted_custs]
        values = [c[1] for c in sorted_custs]
        colors = [CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(labels))]
        bars = ax.barh(labels[::-1], values[::-1], color=colors[::-1],
                       height=0.55, edgecolor="white", linewidth=0.8)
        for bar, val in zip(bars, values[::-1]):
            ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
                    str(val), va="center", ha="left", fontsize=8, color="#2d3748", fontweight="bold")
        ax.set_xlabel("Number of RFQs", fontsize=8, color="#4a5568")
        ax.set_title("RFQs per Customer", fontsize=9, fontweight="bold", color="#2d3748")
        ax.tick_params(axis="y", labelsize=7.5, colors="#4a5568")
        ax.tick_params(axis="x", labelsize=7, colors="#718096")
        ax.set_xlim(0, max(values) * 1.25 if values else 5)
        ax.xaxis.set_major_locator(__import__("matplotlib").ticker.MaxNLocator(integer=True))
        ax.grid(axis="x", linestyle="--", linewidth=0.5, alpha=0.5, color="#cbd5e0")
        fig.tight_layout()

    elif chart_type == "assembly":
        rfq_list = stats.get("rfq_list", [])
        if not rfq_list:
            return None
        # Aggregate assembly counts per customer
        cust_assy = {}
        for r in rfq_list:
            c = r.get("customer", "Unknown")
            cust_assy[c] = cust_assy.get(c, 0) + r.get("assembly_count", 0)
        sorted_data = sorted(cust_assy.items(), key=lambda x: x[1], reverse=True)[:8]
        labels = [d[0][:18] for d in sorted_data]
        values = [d[1] for d in sorted_data]
        colors = [CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(labels))]
        bars = ax.bar(labels, values, color=colors, edgecolor="white", linewidth=0.8, width=0.55)
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                    str(val), ha="center", va="bottom", fontsize=8, color="#2d3748", fontweight="bold")
        ax.set_ylabel("Total Assemblies", fontsize=8, color="#4a5568")
        ax.set_title("Assembly Count per Customer", fontsize=9, fontweight="bold", color="#2d3748")
        ax.tick_params(axis="x", labelsize=7.5, rotation=25, colors="#4a5568")
        ax.tick_params(axis="y", labelsize=7, colors="#718096")
        ax.set_ylim(0, max(values) * 1.3 if values else 5)
        ax.yaxis.set_major_locator(__import__("matplotlib").ticker.MaxNLocator(integer=True))
        ax.grid(axis="y", linestyle="--", linewidth=0.5, alpha=0.5, color="#cbd5e0")
        fig.tight_layout()

    elif chart_type == "overview":
        # 2-panel: stage pie left, customer bar right
        fig = Figure(figsize=(6.8, 3.4), dpi=96, facecolor="#f8fafc")
        ax1 = fig.add_subplot(1, 2, 1, facecolor="#f8fafc")
        ax2 = fig.add_subplot(1, 2, 2, facecolor="#f8fafc")
        for a in [ax1, ax2]:
            for spine in a.spines.values():
                spine.set_edgecolor("#e2e8f0")

        # Pie - stage
        stage_counts = stats.get("stage_counts", {})
        if stage_counts:
            labels_s = list(stage_counts.keys())
            vals_s = list(stage_counts.values())
            colors_s = CHART_COLORS[:len(labels_s)]
            wedges, _, autotexts = ax1.pie(
                vals_s, autopct="%1.0f%%", colors=colors_s, startangle=140,
                wedgeprops=dict(linewidth=1.5, edgecolor="white"), pctdistance=0.72
            )
            for at in autotexts:
                at.set_fontsize(7.5)
                at.set_color("white")
                at.set_fontweight("bold")
            
            # Formatted legend labels with count
            leg_labels = [f"{lbl} ({val})" for lbl, val in zip(labels_s, vals_s)]
            ax1.legend(wedges, leg_labels, loc="upper center", ncol=1,
                       bbox_to_anchor=(0.5, -0.05), fontsize=6.5, frameon=False)
        ax1.set_title("Stage Distribution", fontsize=8.5, fontweight="bold", color="#2d3748")

        # Bar - customers
        cust_counts = stats.get("customer_counts", {})
        if cust_counts:
            sorted_c = sorted(cust_counts.items(), key=lambda x: x[1], reverse=True)[:6]
            lbls = [c[0][:14] for c in sorted_c]
            vals = [c[1] for c in sorted_c]
            colors_c = [CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(lbls))]
            bars = ax2.barh(lbls[::-1], vals[::-1], color=colors_c[::-1],
                            height=0.5, edgecolor="white", linewidth=0.6)
            for bar, val in zip(bars, vals[::-1]):
                ax2.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
                         str(val), va="center", ha="left", fontsize=7.5, color="#2d3748", fontweight="bold")
            ax2.set_xlim(0, max(vals) * 1.3 if vals else 5)
            ax2.xaxis.set_major_locator(__import__("matplotlib").ticker.MaxNLocator(integer=True))
            ax2.tick_params(axis="y", labelsize=7, colors="#4a5568")
            ax2.tick_params(axis="x", labelsize=7, colors="#718096")
            ax2.grid(axis="x", linestyle="--", linewidth=0.5, alpha=0.5, color="#cbd5e0")
        ax2.set_title("RFQs per Customer", fontsize=8.5, fontweight="bold", color="#2d3748")
        fig.suptitle("System RFQ Overview Dashboard", fontsize=10, fontweight="bold", color="#1a202c", y=0.98)
        fig.tight_layout(rect=[0, 0.02, 1, 0.94])

    else:
        return None

    return fig


def detect_chart_intent(text):
    """
    Returns (chart_type, caption) if the prompt is requesting a chart/graph, else (None, None).
    """
    lower = text.lower()
    wants_chart = any(k in lower for k in [
        "graph", "chart", "plot", "draw", "visuali", "pie", "bar chart",
        "histogram", "diagram", "show me", "display"
    ])
    if not wants_chart:
        return None, None

    if any(k in lower for k in ["stage", "status", "distribution", "pipeline"]):
        return "stage", "RFQ Stage Distribution"
    if any(k in lower for k in ["assembl"]):
        return "assembly", "Assembly Count per Customer"
    if any(k in lower for k in ["customer", "client", "who", "top"]):
        return "customer", "RFQs per Customer"
    # Default: overview dashboard
    return "overview", "System RFQ Overview Dashboard"


def _status_to_stage_and_tag(data):
    """Authoritative Project Management stage & tag resolution matching base_panel.py."""
    status = data.get('status')
    s_done_flag = data.get('sourcing_status') in ('completed', 'approved')
    c_done_flag = data.get('cycle_time_status') in ('completed', 'approved')
    if not status or status == 'pending_bom':
        if s_done_flag or c_done_flag or data.get("cycle_time_data") or data.get("nre_data"):
            status = 'pending_sourcing_and_cycle_time'
        else:
            status = 'pending_bom'
            
    if status == 'pending_bom':
        return 'BOM Verification', 'pending_bom'
    if status == 'pending_sourcing_and_cycle_time':
        s_st = data.get('sourcing_status')
        s_done = s_st in ('completed', 'approved')
        c_done = data.get('cycle_time_status') in ('completed', 'approved')
        if s_st == 'partial':
            stage = 'Partial Sourcing Dispatched'
        elif s_done and not c_done:
            stage = 'Pending Cycle Time (Sourcing Done)'
        elif c_done and not s_done:
            stage = 'Pending Sourcing (Cycle Time Done)'
        else:
            stage = 'Pending Sourcing & Cycle Time'
        return stage, 'pending_sourcing'
    if status == 'pending_costing':
        return 'Pending Costing', 'pending_costing'
    if status == 'pending_npi':
        return 'Pending NPI', 'pending_npi'
    if status == 'pending_wi':
        return 'Pending WI', 'pending_wi'
    if status == 'completed':
        return 'Completed', 'completed'
    rp = data.get('revert_pending')
    if rp and not rp.get('acknowledged'):
        target_stage = rp.get('target_stage', 'pending_bom')
        _labels = {
            "pending_bom": "BOM Verification",
            "pending_sourcing_and_cycle_time": "Pending Sourcing & Cycle Time",
            "pending_costing": "Pending Costing",
            "pending_npi": "Pending NPI",
            "pending_wi": "Pending WI",
            "completed": "Completed"
        }
        return _labels.get(target_stage, target_stage), 'revert_pending'
    return status or 'BOM Verification', 'pending_bom'


def get_rfq_summary_stats(server_path=None):
    """Scans BOM_DATA_DIR and gathers real-time statistics on all RFQs in the system."""
    import sys
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ref_bom = os.path.join(base_dir, "ref", "BOM")
    if ref_bom not in sys.path:
        sys.path.insert(0, ref_bom)

    try:
        from utils import BOM_DATA_DIR
        target_dir = BOM_DATA_DIR
    except Exception:
        target_dir = os.path.join(base_dir, "ref", "BOM", "bom_data")

    total_rfqs = 0
    stage_counts = {}
    customer_counts = {}
    rfq_list = []

    if os.path.exists(target_dir):
        for root_dir, dirs, files in os.walk(target_dir):
            for file in files:
                if file.endswith(".json") and not file.endswith("_metadata.json"):
                    file_path = os.path.join(root_dir, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        if isinstance(data, dict):
                            rfq_id = data.get("RFQ") or data.get("rfq_id") or os.path.splitext(file)[0]
                            cust = data.get("Customer") or data.get("customer_name") or "Unknown"
                            
                            # Authoritative stage resolution matching Project Management
                            stage, tag = _status_to_stage_and_tag(data)

                            # Extract assembly count and line item counts
                            assy_list = data.get("Assemblies") or data.get("assemblies") or data.get("BOM Data") or []
                            assy_count = len(assy_list) if isinstance(assy_list, list) and len(assy_list) > 0 else 1
                            
                            line_count = 0
                            if isinstance(assy_list, list):
                                for a in assy_list:
                                    if isinstance(a, dict):
                                        items = a.get("items") or a.get("parts") or []
                                        line_count += len(items) if isinstance(items, list) else 0
                            elif isinstance(data.get("items"), list):
                                line_count = len(data.get("items"))

                            eau = data.get("eau") or data.get("EAU") or "N/A"

                            total_rfqs += 1
                            stage_counts[stage] = stage_counts.get(stage, 0) + 1
                            customer_counts[cust] = customer_counts.get(cust, 0) + 1
                            rfq_list.append({
                                "rfq_id": rfq_id,
                                "customer": cust,
                                "stage": stage,
                                "tag": tag,
                                "assembly_count": assy_count,
                                "line_item_count": line_count,
                                "eau": eau
                            })
                    except Exception:
                        pass

    return {
        "total_rfqs": total_rfqs,
        "stage_counts": stage_counts,
        "customer_counts": customer_counts,
        "rfq_list": rfq_list,
        "bom_data_dir": target_dir
    }

class BrainRouter:
    """
    Central Hybrid AI Engine Router.
    Routes queries to Local Ollama models, Gemini API, OpenAI API, or Rule Fallback Engine
    based on per-module configuration in config.ini.
    """
    def __init__(self, config_path=None):
        if not config_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config.ini")

        self.config_path = config_path
        self.config = configparser.ConfigParser()
        self._load_config()

    def get_rfq_summary(self):
        return get_rfq_summary_stats()

    def answer_system_query(self, prompt, module_key="bom"):
        """Answers arbitrary natural language queries using live database context and LLM reasoning."""
        from agents.prompt_guard import check_prompt

        decision = check_prompt(prompt, module_key)
        if not decision.allowed:
            return decision.user_message

        stats = get_rfq_summary_stats()
        
        system_prompt = (
            "You are the ContinuumX AI Agent Assistant. "
            "Analyze the provided live system database context (RFQs, customers, assembly counts, line items, stages) "
            "and answer the user's specific natural language question accurately and concisely."
        )
        
        res = self.query_model(module_key, prompt, system_prompt, stats)
        # Smart Data Reasoning Fallback when LLM API / Ollama is offline
        prompt_lower = prompt.lower()
        rfqs = stats.get("rfq_list", [])
        custs = stats.get("customer_counts", {})
        total = stats.get("total_rfqs", 0)

        # Check if user commands MOQ assignment (Global or Custom MOQs)
        if any(k in prompt_lower for k in ["moq", " mo ", "moqs", "fill up mo", "add mo", "assign mo"]):
            import re
            rfq_match = re.search(r'\brfq[-_\s]*([a-z0-9_-]+)', prompt, re.IGNORECASE)
            rfq_target = rfq_match.group(1).lower() if rfq_match else None
            rfq_full_str = rfq_match.group(0).lower() if rfq_match else ""

            # Check if prompt contains Custom MOQs per specific assembly
            custom_moq_map = {}
            for line in prompt.splitlines():
                assy_m = re.search(r'\b([a-z0-9_]{2,}(?:-[a-z0-9_]+)+)\b', line, re.IGNORECASE)
                if assy_m:
                    assy_id = assy_m.group(1).strip()
                    nums = [int(n) for n in re.findall(r'\b\d+\b', line.replace(assy_id, '')) if int(n) > 0]
                    if nums:
                        custom_moq_map[assy_id] = nums

            # Extract Global MOQs (numbers outside of specific assembly lines)
            clean_text = prompt.lower().replace(rfq_full_str, '') if rfq_full_str else prompt.lower()
            for k in custom_moq_map:
                clean_text = clean_text.replace(k.lower(), '')
            
            global_moq_list = [int(n) for n in re.findall(r'\b\d+\b', clean_text) if int(n) > 0]
            if not global_moq_list and not custom_moq_map:
                global_moq_list = [100, 200, 300]

            target_dir = stats.get("bom_data_dir")
            matched_file = None
            matched_data = None
            
            if target_dir and os.path.exists(target_dir):
                for root, dirs, files in os.walk(target_dir):
                    for f in files:
                        if f.endswith('.json') and not f.endswith('metadata.json'):
                            fp = os.path.join(root, f)
                            try:
                                with open(fp, 'r', encoding='utf-8') as jf:
                                    d = json.load(jf)
                                r_id = str(d.get('RFQ') or d.get('rfq_id') or os.path.splitext(f)[0]).lower()
                                base_f = os.path.splitext(f)[0].lower()
                                
                                if rfq_target:
                                    t_clean = rfq_target.replace('rfq', '').replace('-', '').replace('_', '')
                                    r_clean = r_id.replace('rfq', '').replace('-', '').replace('_', '')
                                    f_clean = base_f.replace('rfq', '').replace('-', '').replace('_', '')
                                    if r_id == rfq_target or base_f == rfq_target or r_clean == t_clean or f_clean == t_clean:
                                        matched_file = fp
                                        matched_data = d
                                        break
                            except Exception:
                                pass
                    if matched_file:
                        break

            if matched_file and matched_data:
                assys = matched_data.get('Assemblies', [])
                if not assys and isinstance(matched_data.get('assemblies'), list):
                    assys = matched_data['assemblies']
                    
                global_count = 0
                custom_count = 0

                for a in assys:
                    assy_no = a.get('Assy #', '')
                    if assy_no in custom_moq_map:
                        a['Assigned MOQs'] = custom_moq_map[assy_no]
                        a['MOQ Type'] = 'Custom'
                        custom_count += 1
                    elif global_moq_list:
                        a['Assigned MOQs'] = global_moq_list
                        a['MOQ Type'] = 'Global'
                        global_count += 1

                if global_moq_list:
                    matched_data['Global MOQs'] = global_moq_list
                    matched_data['assigned_moqs'] = global_moq_list

                if custom_moq_map:
                    matched_data['custom_moqs'] = custom_moq_map

                with open(matched_file, 'w', encoding='utf-8') as wf:
                    json.dump(matched_data, wf, indent=2)

                cust = matched_data.get('Customer') or matched_data.get('customer_name') or 'Customer'
                rfq_num = matched_data.get('RFQ') or matched_data.get('rfq_id') or (rfq_target.upper() if rfq_target else 'RFQ')
                
                resp_lines = [f"✅ Successfully Updated MOQs for RFQ '{rfq_num}'!\n", f"• Customer: {cust}"]
                if global_moq_list:
                    resp_lines.append(f"• Global MOQs: {', '.join(str(m) for m in global_moq_list)} pcs ({global_count} assemblies)")
                if custom_moq_map:
                    c_details = ", ".join(f"{k} ({', '.join(str(m) for m in v)})" for k, v in custom_moq_map.items())
                    resp_lines.append(f"• Custom MOQs: {c_details} ({custom_count} assemblies)")
                resp_lines.append(f"\nSaved accurately to BOM system with proper Global & Custom MOQ status tags.")
                
                return "\n".join(resp_lines)

        # Specific RFQ Lookup (e.g. "what is the status for rfq 123456" or "details for 123456")
        import re
        rfq_match = re.search(r'\brfq[-_\s]*([a-z0-9_-]+)', prompt_lower)
        target_rfq_id = rfq_match.group(1).lower() if rfq_match else None
        
        if not target_rfq_id:
            for r in rfqs:
                r_id_l = r.get('rfq_id', '').lower()
                if len(r_id_l) > 2 and r_id_l in prompt_lower:
                    target_rfq_id = r_id_l
                    break

        if target_rfq_id and not any(k in prompt_lower for k in ["how many", "total", "chart", "pie", "distribution"]):
            matched_rfq = None
            t_clean = target_rfq_id.replace('rfq', '').replace('-', '').replace('_', '')
            for r in rfqs:
                r_id_l = r.get('rfq_id', '').lower()
                r_clean = r_id_l.replace('rfq', '').replace('-', '').replace('_', '')
                if r_id_l == target_rfq_id or r_clean == t_clean:
                    matched_rfq = r
                    break

            if matched_rfq:
                target_dir = stats.get('bom_data_dir')
                full_data = {}
                if target_dir and os.path.exists(target_dir):
                    for root, dirs, files in os.walk(target_dir):
                        for f in files:
                            if f.endswith('.json') and not f.endswith('metadata.json'):
                                f_base = os.path.splitext(f)[0].lower()
                                f_clean = f_base.replace('rfq', '').replace('-', '').replace('_', '')
                                if f_base == target_rfq_id or f_clean == t_clean:
                                    with open(os.path.join(root, f), 'r', encoding='utf-8') as jf:
                                        full_data = json.load(jf)
                                    break

                rfq_id = matched_rfq.get('rfq_id')
                cust = matched_rfq.get('customer')
                stage = matched_rfq.get('stage')
                assy_cnt = matched_rfq.get('assembly_count', 1)

                moqs_list = []
                if full_data.get('Assemblies'):
                    moqs_list = full_data['Assemblies'][0].get('Assigned MOQs', [])
                elif full_data.get('assigned_moqs'):
                    moqs_list = full_data.get('assigned_moqs', [])
                moq_str = ', '.join(str(m) for m in moqs_list) if moqs_list else 'Not Assigned'

                created = full_data.get('created_at') or full_data.get('bom_creation_date') or 'N/A'
                pic = full_data.get('bom_assigned_by') or full_data.get('dispatched_by') or 'Sysadmin'

                return (f"📌 Status & Details for RFQ '{rfq_id}':\n\n"
                        f"• Current Stage: {stage}\n"
                        f"• Customer Name: {cust}\n"
                        f"• Assigned MOQs: {moq_str}\n"
                        f"• Total Assemblies: {assy_cnt}\n"
                        f"• Creation Timestamp: {created}\n"
                        f"• Assigned PIC: {pic}")

        # Stage-specific filtering queries (e.g. "which RFQs are pending from sourcing?")
        target_stage_term = None
        if "sourcing" in prompt_lower: target_stage_term = "sourcing"
        elif "costing" in prompt_lower: target_stage_term = "costing"
        elif "npi" in prompt_lower: target_stage_term = "npi"
        elif "bom" in prompt_lower or "verification" in prompt_lower: target_stage_term = "bom"
        elif re.search(r'\bwi\b', prompt_lower) or "work instruction" in prompt_lower: target_stage_term = "wi"
        elif "completed" in prompt_lower or "done" in prompt_lower: target_stage_term = "completed"

        if target_stage_term:
            matched_rfqs = [
                r for r in rfqs
                if target_stage_term in r.get("stage", "").lower() or target_stage_term in r.get("tag", "").lower()
            ]
            if matched_rfqs:
                lines = [f"  • {r['rfq_id']} — Customer: {r['customer']} (Stage: {r['stage']})" for r in matched_rfqs]
                return (f"📋 Found {len(matched_rfqs)} RFQ(s) in the '{target_stage_term.upper()}' stage:\n\n" +
                        "\n".join(lines))
            else:
                return f"ℹ️ Currently, there are 0 RFQs in the '{target_stage_term.upper()}' stage."

        if "assembly" in prompt_lower or "assemblies" in prompt_lower:
            if rfqs:
                max_assy_rfq = max(rfqs, key=lambda x: x.get("assembly_count", 0))
                return (f"📊 Data Insight:\n"
                        f"Customer '{max_assy_rfq['customer']}' has the highest assembly count in a single RFQ "
                        f"(RFQ ID: '{max_assy_rfq['rfq_id']}' with {max_assy_rfq['assembly_count']} assembly(ies) "
                        f"and {max_assy_rfq.get('line_item_count', 0)} line item(s)).")
        
        if "customer" in prompt_lower and ("most" in prompt_lower or "highest" in prompt_lower or "top" in prompt_lower):
            if custs:
                top_cust = max(custs.items(), key=lambda x: x[1])
                return (f"📊 Data Insight:\n"
                        f"Customer '{top_cust[0]}' has created the most RFQs in your system ({top_cust[1]} RFQs out of {total} total).")

        if any(k in prompt_lower for k in ["how many rfq", "total rfq", "rfq summary", "stage summary", "system summary", "count of rfq", "stage distribution", "rfq count"]):
            stage_lines = [f"   - {st}: {cnt}" for st, cnt in stats.get("stage_counts", {}).items()]
            return (f"📊 System RFQ Summary Report:\n\n"
                    f"• Total RFQs Created in System: {total} RFQs\n\n"
                    f"• Current Stage Distribution:\n" + "\n".join(stage_lines))

        return None

    def extract_parameters_with_llm(self, text, context=None):
        """
        Uses configured LLM (e.g. Gemini) to extract structured manufacturing parameters from user chat.
        Seamlessly falls back to deterministic parameter_parser if LLM is unavailable.
        """
        system_instruction = (
            "You are the central ContinuumX Manufacturing Intelligence Parser.\n"
            "Extract structured BOM parameters from the user's input.\n"
            "Respond ONLY with a valid JSON object with these keys:\n"
            "{\n"
            '  "customer_name": string or null,\n'
            '  "project_title": string or null,\n'
            '  "commodity": "PCBA" | "Wire Harness" | "FIBER Optic" | "BoxBuild" | "Module" or null,\n'
            '  "rfq_number": string or null,\n'
            '  "target_price": string (e.g. "$12.50") or null,\n'
            '  "eau": string (e.g. "5000") or null,\n'
            '  "default_moqs": list of integers (e.g. [200, 300, 500, 600]),\n'
            '  "custom_moqs": dict of assembly_id -> list of integers,\n'
            '  "should_launch": boolean (true if user says proceed/launch/start/open/confirm),\n'
            '  "conversational_reply": string (polite summary of what was updated)\n'
            "}"
        )

        try:
            llm_res = self.query_model("brain", text, system_prompt=system_instruction, context_data=context)
            if llm_res.get("success") and llm_res.get("response"):
                raw_resp = llm_res["response"].strip()
                if raw_resp.startswith("```"):
                    raw_resp = re.sub(r'^```(?:json)?\s*', '', raw_resp)
                    raw_resp = re.sub(r'\s*```$', '', raw_resp)
                parsed = json.loads(raw_resp)
                if isinstance(parsed, dict):
                    has_updates = any([
                        parsed.get("customer_name"),
                        parsed.get("project_title"),
                        parsed.get("commodity"),
                        parsed.get("rfq_number"),
                        parsed.get("target_price"),
                        parsed.get("eau"),
                        parsed.get("default_moqs"),
                        parsed.get("custom_moqs")
                    ])
                    parsed["has_updates"] = has_updates
                    parsed["llm_powered"] = True
                    return parsed
        except Exception as e:
            print(f"[BrainRouter LLM Extraction Notice] {e}")

        # Local rule-engine fallback
        from agents.parameter_parser import parse_bom_parameters
        fallback_res = parse_bom_parameters(text)
        fallback_res["llm_powered"] = False
        return fallback_res

    def _load_config(self):
        if os.path.exists(self.config_path):
            try:
                self.config.read(self.config_path, encoding='utf-8')
            except Exception as e:
                print(f"[BrainRouter] Warning reading config.ini: {e}")

    def get_agent_config(self, module_key):
        """Returns (provider, model) tuple for a specific module agent."""
        self._load_config()
        section = "AGENTS_LLM"
        provider_key = f"{module_key.lower().replace(' ', '')}_agent_provider"
        model_key = f"{module_key.lower().replace(' ', '')}_agent_model"

        provider = "local"
        model = "qwen2.5"

        if section in self.config:
            provider = self.config[section].get(provider_key, "local").strip().lower()
            model = self.config[section].get(model_key, "qwen2.5").strip()

        return provider, model

    def query_model(self, module_key, prompt, system_prompt=None, context_data=None):
        """
        Main query entrypoint for agents.
        Dispatches prompt to configured provider (local / gemini / openai) with fallback.
        """
        from agents.prompt_guard import check_prompt

        decision = check_prompt(prompt, module_key)
        if not decision.allowed:
            return {
                "success": False,
                "rejected": True,
                "provider": "prompt_guard",
                "error": decision.rule_id,
                "response": decision.user_message,
            }

        provider, model = self.get_agent_config(module_key)
        
        full_system_prompt = system_prompt or f"You are the specialized AI Agent for the {module_key} module in ContinuumX."
        if context_data:
            full_system_prompt += f"\nContext Data:\n{json.dumps(context_data, indent=2)}"

        if provider == "gemini":
            return self._query_gemini(prompt, full_system_prompt, model)
        elif provider == "openai":
            return self._query_openai(prompt, full_system_prompt, model)
        else:
            # Default to local Ollama with fallback
            return self._query_ollama(prompt, full_system_prompt, model)

    def _query_ollama(self, prompt, system_prompt, model="qwen2.5"):
        """Queries local Ollama instance (http://localhost:11434)."""
        ollama_endpoint = "http://localhost:11434"
        if "AGENTS_LLM" in self.config and "ollama_endpoint" in self.config["AGENTS_LLM"]:
            ollama_endpoint = self.config["AGENTS_LLM"]["ollama_endpoint"].strip()

        url = f"{ollama_endpoint}/api/generate"
        payload = {
            "model": model,
            "prompt": f"System: {system_prompt}\nUser: {prompt}\nAssistant:",
            "stream": False
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    resp_data = json.loads(response.read().decode('utf-8'))
                    return {
                        "success": True,
                        "provider": f"local:ollama/{model}",
                        "response": resp_data.get("response", "").strip()
                    }
        except Exception as e:
            # Fallback to local rule engine notice
            return {
                "success": False,
                "provider": f"local:rule-engine",
                "error": f"Ollama local service not reachable ({e}). Used rule engine fallback.",
                "response": None
            }

    def _query_gemini(self, prompt, system_prompt, model="gemini-2.5-flash"):
        """Queries Google Gemini REST API."""
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key and "AGENTS_LLM" in self.config:
            api_key = self.config["AGENTS_LLM"].get("gemini_api_key", "").strip()

        if not api_key:
            return {
                "success": False,
                "provider": "gemini",
                "error": "Gemini API Key missing in config.ini or GEMINI_API_KEY environment variable.",
                "response": None
            }

        # Normalize legacy model names to available models
        legacy_map = {
            "gemini-2.0-flash": "gemini-flash-latest",
            "gemini-flash": "gemini-flash-latest",
            "gemini-1.5-flash": "gemini-flash-latest",
            "gemini-2.5-flash": "gemini-flash-latest",
            "gemini-1.5-pro": "gemini-pro-latest",
            "gemini-2.5-pro": "gemini-pro-latest",
        }
        model = legacy_map.get(model, model)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": f"System Instruction: {system_prompt}"},
                    {"text": prompt}
                ]
            }]
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    res_json = json.loads(response.read().decode('utf-8'))
                    text = res_json['candidates'][0]['content']['parts'][0]['text']
                    return {
                        "success": True,
                        "provider": f"gemini:{model}",
                        "response": text.strip()
                    }
        except Exception as e:
            return {"success": False, "provider": "gemini", "error": str(e), "response": None}

    def _query_openai(self, prompt, system_prompt, model="gpt-4o"):
        """Queries OpenAI REST API."""
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key and "AGENTS_LLM" in self.config:
            api_key = self.config["AGENTS_LLM"].get("openai_api_key", "").strip()

        if not api_key:
            return {
                "success": False,
                "provider": "openai",
                "error": "OpenAI API Key missing in config.ini or OPENAI_API_KEY environment variable.",
                "response": None
            }

        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    res_json = json.loads(response.read().decode('utf-8'))
                    text = res_json['choices'][0]['message']['content']
                    return {
                        "success": True,
                        "provider": f"openai:{model}",
                        "response": text.strip()
                    }
        except Exception as e:
            return {"success": False, "provider": "openai", "error": str(e), "response": None}

    def check_rfq_emails(self, limit=5, unread_only=False, subject_filter=None, progress_callback=None):
        """
        Connects to IMAP inbox (aitinkteng03@gmail.com), fetches recent emails,
        classifies RFQs, and extracts structured BOM data + generates synthetic Excel.

        Args:
            limit:             Max number of emails to scan (default 5 for token efficiency).
            unread_only:       Only scan unread messages.
            subject_filter:    Optional string (e.g. 'RS26-8300', 'Tecan') to only process matching emails.
            progress_callback: Optional callable(status_str) for live UI progress updates.
        """
        try:
            from agents.email_fetcher import EmailFetcher
            from agents.multimodal_extractor import MultimodalExtractor
            from agents.synthetic_bom_generator import SyntheticBOMGenerator

            scan_limit = max(limit, 50)
            fetcher = EmailFetcher(self.config_path)
            fetch_res = fetcher.fetch_recent_emails(limit=scan_limit, unread_only=unread_only, filter_rfq=False)

            if not fetch_res.get("success"):
                return {
                    "success": False,
                    "error": fetch_res.get("error", "Failed to connect to email inbox"),
                    "emails": []
                }

            all_emails = fetch_res.get("emails", [])
            rfq_emails = [e for e in all_emails if e.get("classification", {}).get("is_rfq_related")]

            # Apply user subject / keyword filter if provided
            if subject_filter and str(subject_filter).strip():
                sf = str(subject_filter).strip().lower()
                filtered = [e for e in rfq_emails if sf in e.get("subject", "").lower() or sf in e.get("body", "").lower()]
                if filtered:
                    rfq_emails = filtered
                else:
                    # Also check all emails in case non-rfq heuristic misclassified it
                    filtered_all = [e for e in all_emails if sf in e.get("subject", "").lower() or sf in e.get("body", "").lower()]
                    if filtered_all:
                        rfq_emails = filtered_all
                if filtered:
                    rfq_emails = filtered

            all_emails_count = fetch_res.get("count", 0)

            extractor = MultimodalExtractor(self.config_path)
            generator = SyntheticBOMGenerator()

            from agents.telemetry_tracker import ProcessingTelemetryTracker
            tracker = ProcessingTelemetryTracker()

            processed_rfqs = []
            for idx, em in enumerate(rfq_emails, start=1):
                t_start = time.time()
                subj = em.get("subject", f"Email {idx}")[:40]
                if progress_callback:
                    progress_callback(f"📩 [{idx}/{len(rfq_emails)}] Processing: {subj}...")
                rfq_json = extractor.extract_full_rfq(em, progress_callback=progress_callback)
                synth_res = generator.generate_synthetic_excel(rfq_json)
                t_end = time.time()

                # Record Telemetry Metrics
                rfq_no = rfq_json.get("rfq_metadata", {}).get("rfq_number", "")
                assy_cnt = len(rfq_json.get("assemblies", []))
                comp_cnt = sum(len(a.get("items", [])) for a in rfq_json.get("assemblies", []))
                att_cnt = len(em.get("attachments", []))
                telemetry_rec = tracker.record_run(
                    email_subject=em.get("subject", subj),
                    rfq_number=rfq_no,
                    start_time=t_start,
                    end_time=t_end,
                    assemblies_count=assy_cnt,
                    components_count=comp_cnt,
                    attachments_count=att_cnt
                )

                processed_rfqs.append({
                    "email": em,
                    "rfq_json": rfq_json,
                    "synthetic_bom": synth_res,
                    "telemetry": telemetry_rec
                })

            return {
                "success": True,
                "email_address": fetch_res.get("email_address"),
                "total_scanned": all_emails_count,
                "rfq_count": len(rfq_emails),
                "rfqs": processed_rfqs,
                "recent_emails_summary": [
                    {
                        "subject": e["subject"],
                        "from": e["sender"],
                        "date": e["date"],
                        "intent": e["classification"]["intent"],
                        "confidence": e["classification"]["confidence"],
                        "attachments_count": len(e.get("attachments", []))
                    }
                    for e in fetch_res.get("emails", [])
                ]
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Email RFQ processing error: {e}",
                "rfqs": []
            }

if __name__ == "__main__":
    router = BrainRouter()
    print("BOM Agent Config:", router.get_agent_config("bom"))
    print("Sourcing Agent Config:", router.get_agent_config("sourcing"))
    print("Test Local Query:", router.query_model("bom", "Hello agent!"))

