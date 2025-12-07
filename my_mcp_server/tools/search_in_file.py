import os
def register(server):
    @server.tool()
    def search_in_file(
        path: str,
        query: str,
        case_sensitive: bool = False,
        max_results: int = 100,
        max_bytes: int = 200_000
    ) -> dict:
        try:
            path = os.path.abspath(os.path.expanduser(path))
            if not os.path.exists(path):
                return {"error": f"File does not exist: {path}"}
            if not os.path.isfile(path):
                return {"error": f"Path is not a file: {path}"}
            if not query or not isinstance(query, str):
                return {"error": "Query must be a non-empty string"}
            file_size = os.path.getsize(path)
            if file_size > max_bytes:
                return {
                    "error": f"File too large to search ({file_size} bytes). "
                             f"Max allowed is {max_bytes} bytes."
                }
            matches = []
            with open(path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    src_line = line.rstrip("\n")
                    haystack = src_line if case_sensitive else src_line.lower()
                    needle = query if case_sensitive else query.lower()
                    if needle in haystack:
                        pos = haystack.index(needle)
                        matches.append({
                            "line_number": line_num,
                            "content": src_line,
                            "position": pos
                        })
                    if len(matches) >= max_results:
                        break
            return {
                "success": True,
                "path": path,
                "query": query,
                "case_sensitive": case_sensitive,
                "total_matches": len(matches),
                "matches": matches,
                "truncated": len(matches) >= max_results,
                "message": f"Found {len(matches)} matches in {path}"
            }
        except UnicodeDecodeError:
            return {"error": f"File is not UTF-8 text: {path}"}
        except PermissionError:
            return {"error": f"Permission denied: {path}"}
        except Exception as e:
            return {"error": f"Error searching file: {str(e)}"}
