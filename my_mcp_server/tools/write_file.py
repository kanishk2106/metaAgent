import os
def register(server):
    @server.tool()
    def write_file(
        path: str,
        content: str,
        mode: str = "overwrite",
        max_bytes: int = 200_000
    ) -> dict:
        try:
            path = os.path.abspath(os.path.expanduser(path))
            if not isinstance(content, str):
                return {"error": "content must be a string"}
            if len(content.encode("utf-8")) > max_bytes:
                return {
                    "error": f"Content too large ({len(content)} bytes). "
                             f"Max allowed is {max_bytes} bytes."
                }
            mode = mode.lower()
            if mode not in ["overwrite", "append"]:
                return {"error": "mode must be 'overwrite' or 'append'"}
            parent_dir = os.path.dirname(path)
            if parent_dir and not os.path.exists(parent_dir):
                if ".." in parent_dir:
                    return {"error": "Directory traversal not allowed"}
                os.makedirs(parent_dir, exist_ok=True)
            file_mode = "w" if mode == "overwrite" else "a"
            with open(path, file_mode, encoding="utf-8") as f:
                written = f.write(content)
            return {
                "success": True,
                "path": path,
                "mode": mode,
                "bytes_written": written,
                "message": f"Wrote {written} bytes to {path} ({mode})"
            }
        except PermissionError:
            return {"error": f"Permission denied: {path}"}
        except Exception as e:
            return {"error": f"Error writing file: {str(e)}"}
