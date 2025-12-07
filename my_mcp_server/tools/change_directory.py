import os
def register(server):
    @server.tool()
    def change_directory(path: str) -> dict:
        try:
            path = os.path.abspath(path)
            if not os.path.exists(path):
                return {"error": f"Path does not exist: {path}"}
            if not os.path.isdir(path):
                return {"error": f"Path is not a directory: {path}"}
            old_cwd = os.getcwd()
            os.chdir(path)
            new_cwd = os.getcwd()
            return {
                "success": True,
                "previous_directory": old_cwd,
                "current_directory": new_cwd,
                "message": f"Changed directory to {new_cwd}"
            }
        except PermissionError:
            return {"error": f"Permission denied: {path}"}
        except Exception as e:
            return {"error": f"Failed to change directory: {str(e)}"}
