import json
import os
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
BLUEPRINT_PATH = os.path.join(BASE_DIR, "blueprint/blueprint.sone")
LEDGER_PATH = os.path.join(BASE_DIR, "ledger/ledger.jsonl")
STATUS_PATH = os.path.join(BASE_DIR, "state/status.json")
DASHBOARD_PATH = os.path.join(BASE_DIR, "dashboard/index.html")

def load_json(path):
    if not os.path.exists(path): return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def compile_state():
    if not os.path.exists(BLUEPRINT_PATH):
        print(f"❌ Blueprint not found at {BLUEPRINT_PATH}")
        return

    # 1. Load Blueprint (Baseline)
    with open(BLUEPRINT_PATH, "r", encoding="utf-8") as f:
        # Assuming blueprint.sone is JSON for now, as per instruction
        blueprint = json.load(f)

    nodes = {n["id"]: {**n, "logs": [], "current_status": "TODO"} for n in blueprint.get("nodes", [])}
    
    # 2. Replay Ledger
    if os.path.exists(LEDGER_PATH):
        with open(LEDGER_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                try:
                    entry = json.loads(line)
                    node_id = entry.get("node_id")
                    if node_id in nodes:
                        nodes[node_id]["logs"].append(entry)
                        nodes[node_id]["current_status"] = entry["status"]
                        nodes[node_id]["last_updated"] = entry["ts"]
                    else:
                        # SCOPE CREEP DETECTED
                        print(f"⚠️ Scope Creep: Unknown node {node_id}")
                except json.JSONDecodeError:
                    pass

    # 3. Update Status.json
    status_data = {
        "project": blueprint.get("project"),
        "version": blueprint.get("version"),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "nodes": nodes
    }
    save_json(STATUS_PATH, status_data)

    # 4. Generate Dashboard
    generate_dashboard(nodes)
    print("✅ System State Compiled & Dashboard Updated")

def generate_dashboard(nodes):
    # Generate Mermaid Graph
    graph_lines = ["graph TD"]
    style_lines = []
    
    for node_id, node in nodes.items():
        clean_id = node_id.replace(".", "_")
        parent = node.get("parent", "")
        clean_parent = parent.replace(".", "_")
        
        label = f"{node['label']}<br/>({node['current_status']})"
        graph_lines.append(f"{clean_id}[\"{label}\"]")
        
        if parent:
            graph_lines.append(f"{clean_parent} --> {clean_id}")
            
        # Styling
        color = "#999"
        if node["current_status"] == "DONE": color = "#4CAF50"
        elif node["current_status"] == "IN_PROGRESS": color = "#2196F3"
        elif node["current_status"] == "BLOCKED": color = "#F44336"
        
        style_lines.append(f"style {clean_id} fill:{color},stroke:#333,stroke-width:2px,color:#fff")

    mermaid_code = "\n".join(graph_lines + style_lines)

    # Inject into HTML
    with open(DASHBOARD_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    # Simple template injection
    # In a real scenario, we'd use a proper template engine or DOM manipulation script
    # For now, we'll just replace the diagram div content via string manipulation for this single-file logic
    
    # Actually, better to just modify the JS data object and let the frontend render (or re-render)
    # But since we need to overwrite the file with 'updated' content...
    
    # Let's inject the data into the PROJECT_DATA const
    json_str = json.dumps({"nodes": nodes}, ensure_ascii=False)
    
    import re
    # Update PROJECT_DATA
    html = re.sub(r"const PROJECT_DATA = \{.*?\};", f"const PROJECT_DATA = {json_str};", html, flags=re.DOTALL)
    
    # Update Mermaid Content
    # We'll use a placeholder in the HTML or just replace the div content logic in JS?
    # The requirement is "Overwrite" the file.
    # Let's verify the HTML structure. We put `%% Diagram will be injected here` in the div.
    
    html = re.sub(
        r'<div class="mermaid" id="diagram">.*?</div>', 
        f'<div class="mermaid" id="diagram">\n{mermaid_code}\n</div>', 
        html, 
        flags=re.DOTALL
    )

    with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    compile_state()
