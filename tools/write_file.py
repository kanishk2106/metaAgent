def write_file(path: str, content: str):
    with open(path, 'w') as f:
        f.write(content)
    return {"result": None}
