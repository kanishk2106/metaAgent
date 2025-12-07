def read_file(path: str):
    with open(path, 'r') as f:
        content = f.read()
    return {"result": content}
