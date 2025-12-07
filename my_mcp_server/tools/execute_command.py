import subprocess
import shlex
def register(server):
    @server.tool()
    def execute_command(command: str, timeout: int = 10) -> dict:
        allowed_commands = ["ls", "pwd", "whoami", "echo", "date"]
        try:
            parts = shlex.split(command)
            if not parts:
                return {"error": "Empty command"}
            cmd = parts[0]
            if cmd not in allowed_commands:
                return {
                    "error": f"Command '{cmd}' is not allowed.",
                    "allowed": allowed_commands
                }
            result = subprocess.run(
                parts,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout
            )
            return {
                "success": True,
                "command": command,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "message": f"Command '{cmd}' executed safely"
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Command timed out after {timeout} seconds"}
        except Exception as e:
            return {"error": f"Execution failed: {str(e)}"}
