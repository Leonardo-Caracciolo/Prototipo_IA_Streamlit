import os

def guardar_archivo(file, workspace, tipo="documents"):
    folder = f"storage/workspaces/{workspace}/{tipo}"
    if not os.path.exists(folder):
        os.makedirs(folder)
    file_path = os.path.join(folder, file.name)
    with open(file_path, "wb") as f:
        f.write(file.read())
    return file_path