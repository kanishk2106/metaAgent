import os
def register(server):
    @server.tool()
    def get_current_directory() -> dict:
        try:
            cwd = os.getcwd()
            return {
                "success": True,
                "current_directory": cwd,
                "absolute_path": os.path.abspath(cwd),
                "message": f"Current directory: {cwd}"
            }
        except Exception as e:
            return {"error": f"Failed to get current directory: {str(e)}"}
