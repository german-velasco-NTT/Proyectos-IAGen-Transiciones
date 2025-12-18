import json
import os
from pathlib import Path

OUTPUT_DIR = Path("outputs")

def verify_counts():
    print("🔎 Verifying dependency counts...")
    
    # Find latest job
    jobs = sorted([j for j in OUTPUT_DIR.iterdir() if j.is_dir()], key=lambda x: x.stat().st_mtime, reverse=True)
    if not jobs:
        print("❌ No job outputs found")
        return

    latest = jobs[0]
    print(f"📂 Analyzing job: {latest.name}")
    
    # Read graph
    graph_file = latest / "dependency_graph.json"
    if not graph_file.exists():
        print("❌ Graph file not found")
        return
        
    with open(graph_file) as f:
        graph = json.load(f)
        
    edges = graph.get('edges', [])
    stats = graph.get('statistics', {})
    
    print(f"📊 Graph Edges (Raw): {len(edges)}")
    print(f"📊 Stats Connections: {stats.get('connections', 'MISSING')}")
    
    # Read raw deps
    deps_file = latest / "dependencies_by_project.json"
    if deps_file.exists():
        with open(deps_file) as f:
            deps = json.load(f)
            total_raw = sum(len(d) if isinstance(d, list) else len(d.get('files', [])) for d in deps.values())
            print(f"📊 Total Raw Dependencies in Code: {total_raw}")

if __name__ == "__main__":
    verify_counts()
