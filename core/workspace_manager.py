import os

BASE_PATH = "storage/workspaces"

def get_all_workspaces():
    if not os.path.exists(BASE_PATH):
        os.makedirs(BASE_PATH)
    return sorted([d for d in os.listdir(BASE_PATH) if os.path.isdir(os.path.join(BASE_PATH, d))])

def create_workspace(name):
    slug = name.lower().replace(" ", "_")
    path = os.path.join(BASE_PATH, slug)
    if not os.path.exists(path):
        os.makedirs(os.path.join(path, "documents"))
        os.makedirs(os.path.join(path, "knowledge"))
        os.makedirs(os.path.join(path, "threads"))
        with open(os.path.join(path, "history.json"), "w") as f:
            f.write("[]")
    return slug

def delete_workspace(slug):
    import shutil
    path = os.path.join(BASE_PATH, slug)
    if os.path.exists(path):
        shutil.rmtree(path)
        return True
    return False


def detectar_tipo_workspace(workspace_slug: str) -> str:
    path = os.path.join(BASE_PATH, workspace_slug)
    tiene_sql = os.path.exists(os.path.join(path, "sql"))
    tiene_vector = os.path.exists(os.path.join(path, "vectorstore"))

    if tiene_sql and tiene_vector:
        return "mixto"
    elif tiene_sql:
        return "sql"
    elif tiene_vector:
        return "vectorial"
    else:
        return "vacío"
