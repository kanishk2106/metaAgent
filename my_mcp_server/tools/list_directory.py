import os
def register(server):
    @server.tool()
    def list_directory(path: str = ".") -> dict:
        try:
            path = os.path.abspath(os.path.expanduser(path))
            if not os.path.exists(path):
                return {"error": f"Path does not exist: {path}"}
            if not os.path.isdir(path):
                return {"error": f"Path is not a directory: {path}"}
            items = os.listdir(path)
            detailed_items = []
            for item in items:
                item_path = os.path.join(path, item)
                is_dir = os.path.isdir(item_path)
                is_link = os.path.islink(item_path)
                detailed_items.append({
                    "name": item,
                    "type": "directory" if is_dir else "file",
                    "absolute_path": os.path.abspath(item_path),
                    "is_symlink": is_link
                })
            return {
                "success": True,
                "path": path,
                "count": len(detailed_items),
                "items": detailed_items,
                "message": f"Listed {len(detailed_items)} items in {path}"
            }
        except PermissionError:
            return {"error": f"Permission denied: {path}"}
        except Exception as e:
            return {"error": f"Error listing directory: {str(e)}"}
