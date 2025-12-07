import os
def register(server):
    @server.tool()
    def read_file(
        path: str,
        start_line: int | None = None,
        end_line: int | None = None,
        max_bytes: int = 200_000
    ) -> dict:
        try:
            path = os.path.abspath(os.path.expanduser(path))
            if not os.path.exists(path):
                return {"error": f"File does not exist: {path}"}
            if not os.path.isfile(path):
                return {"error": f"Path is not a file: {path}"}
            file_size = os.path.getsize(path)
            if file_size > max_bytes:
                return {
                    "error": f"File too large ({file_size} bytes). "
                             f"Max allowed is {max_bytes} bytes."
                }
            with open(path, "r", encoding="utf-8") as f:
                if start_line is not None or end_line is not None:
                    if start_line is not None and start_line < 1:
                        return {"error": "start_line must be >= 1"}
                    if end_line is not None and end_line < 1:
                        return {"error": "end_line must be >= 1"}
                    lines = f.readlines()
                    start = (start_line - 1) if start_line else 0
                    end = end_line if end_line else len(lines)
                    if start >= len(lines):
                        return {"error": "start_line beyond file length"}
                    if end < start:
                        return {"error": "end_line must be >= start_line"}
                    content = "".join(lines[start:end])
                else:
                    content = f.read()
            return {
                "success": True,
                "path": path,
                "size": len(content),
                "content": content,
                "message": f"Read {len(content)} bytes from {path}"
            }
        except UnicodeDecodeError:
            return {"error": f"File is not UTF-8 text: {path}"}
        except PermissionError:
            return {"error": f"Permission denied: {path}"}
        except Exception as e:
            return {"error": f"Error reading file: {str(e)}"}
