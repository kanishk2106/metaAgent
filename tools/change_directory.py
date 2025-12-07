import os
def change_directory(path: str):
    os.chdir(path)
    return {"result": None}
