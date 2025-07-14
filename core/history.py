import os
import json

def get_history_path(workspace):
    return f"storage/workspaces/{workspace}/history.json"

def load_history(workspace):
    path = get_history_path(workspace)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_history(workspace, history):
    path = get_history_path(workspace)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
