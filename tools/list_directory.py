import os
def list_directory(path: str):
    return {"result": os.listdir(path)}
