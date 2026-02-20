import os
import re
from typing import List, Dict, Any

class BlueprintNode:
    def __init__(self, id: str, label: str, type: str, status: str = "PENDING"):
        self.id = id
        self.label = label
        self.type = type # feature, item
        self.status = status # PENDING, DONE
        self.children = []

    def to_dict(self):
        return {
            "id": self.id,
            "label": self.label,
            "type": self.type,
            "status": self.status,
            "children": [c.to_dict() for c in self.children]
        }

class BlueprintEngine:
    def __init__(self, specs_dir: str = None, code_dir: str = "."):
        from core.engine.constants import SOPHIA_DOCS
        self.specs_dir = specs_dir or SOPHIA_DOCS
        self.code_dir = code_dir
        self.tree = [] # List of BlueprintNode
        self.missing_features = []

    def scan(self):
        """
        1. Parse Specs -> Build Tree (Planned)
        2. Read Ledger -> Update Status (Actual)
        * No Code Scan *
        """
        self.tree = self._parse_specs()
        self._sync_status_from_ledger(self.tree)
        return self.tree

    def _parse_specs(self) -> List[BlueprintNode]:
        nodes = []
        if not self.specs_dir or not os.path.exists(self.specs_dir):
            return nodes

        for filename in os.listdir(self.specs_dir):
            if not filename.endswith(".md"):
                continue
            
            filepath = os.path.join(self.specs_dir, filename)
            with open(filepath, 'r') as f:
                content = f.read()
            
            # File Node
            file_node = BlueprintNode(f"file:{filename}", filename, "spec_file", "DONE")
            
            # Simple Parser for "# Feature:" and "- [ ] Item"
            current_feature = None
            
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith("# Feature:") or line.startswith("## Feature:"):
                    label = line.split(":", 1)[1].strip()
                    current_feature = BlueprintNode(f"feat:{filename}:{label}", label, "feature")
                    file_node.children.append(current_feature)
                elif line.startswith("- [ ]") or line.startswith("- [x]"):
                    if current_feature:
                        label = line.replace("- [ ]", "").replace("- [x]", "").strip()
                        # ID based on label content (simplified)
                        node_id = f"item:{label[:20].replace(' ', '_')}"
                        item_node = BlueprintNode(node_id, label, "item")
                        current_feature.children.append(item_node)
            
            nodes.append(file_node)
            
        return nodes

    def _sync_status_from_ledger(self, nodes: List[BlueprintNode]):
        self.missing_features = []
        # TODO: Read from ledger.jsonl
        # For Phase 2.8, we just mark everything as PLANNED unless manual override
        # This will be connected to Roots later.
        pass

    def get_graph_data(self):
        # Convert Tree to Graph (Nodes/Links)
        nodes = []
        links = []
        
        def traverse(node):
            nodes.append({
                "id": node.id,
                "label": node.label,
                "group": node.type,
                "status": node.status
            })
            for c in node.children:
                links.append({"source": node.id, "target": c.id, "value": 1})
                traverse(c)
        
        for root in self.tree:
            traverse(root)
            
        return {"nodes": nodes, "links": links}

    def get_missing_report(self):
        return self.missing_features
