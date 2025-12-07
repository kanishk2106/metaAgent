import os
import subprocess
import shlex
from typing import Optional, Dict, Any, Union
def register(server):
    @server.tool()
    def execute_command_with_chained_ops(
        command: str,
        command_timeout: int = 10,
        change_to_directory: Optional[str] = None,
        get_cwd_after_cd: bool = False,
        list_target_directory: Optional[str] = None,
        read_target_file: Optional[str] = None,
        read_file_start_line: Optional[int] = None,
        read_file_end_line: Optional[int] = None,
        write_target_file: Optional[str] = None,
        write_file_content: Optional[str] = None,
        write_file_mode: str = "overwrite",
        second_command: Optional[str] = None,
        second_command_timeout: int = 10,
    ) -> Dict[str, Any]:
        results: Dict[str, Any] = {
            "success": False,
            "message": "No operations performed yet.",
            "operations": {}
        }
        MAX_FILE_BYTES = 200_000
        ALLOWED_COMMANDS = ["ls", "pwd", "whoami", "echo", "date"]
        try:
            if change_to_directory is not None:
                try:
                    path = os.path.abspath(change_to_directory)
                    if not os.path.exists(path):
                        return {"error": f"Path does not exist: {path}"}
                    if not os.path.isdir(path):
                        return {"error": f"Path is not a directory: {path}"}
                    old_cwd = os.getcwd()
                    os.chdir(path)
                    new_cwd = os.getcwd()
                    results["operations"]["change_directory"] = {
                        "success": True,
                        "previous_directory": old_cwd,
                        "current_directory": new_cwd,
                    }
                except PermissionError:
                    return {"error": f"Permission denied to change directory: {path}"}
                except Exception as e:
                    return {"error": f"Failed to change directory: {str(e)}"}
            if get_cwd_after_cd and "change_directory" in results["operations"]:
                try:
                    cwd = os.getcwd()
                    results["operations"]["get_current_directory_after_cd"] = {
                        "success": True,
                        "current_directory": cwd,
                        "absolute_path": os.path.abspath(cwd),
                    }
                except Exception as e:
                    return {"error": f"Failed to get current directory: {str(e)}"}
            try:
                parts = shlex.split(command)
                if not parts:
                    return {"error": "Empty primary command"}
                cmd_name = parts[0]
                if cmd_name not in ALLOWED_COMMANDS:
                    return {
                        "error": f"Primary command '{cmd_name}' is not allowed.",
                        "allowed": ALLOWED_COMMANDS,
                    }
                cmd_result = subprocess.run(
                    parts,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=command_timeout,
                )
                results["operations"]["primary_command_execution"] = {
                    "success": True,
                    "command": command,
                    "stdout": cmd_result.stdout,
                    "stderr": cmd_result.stderr,
                    "returncode": cmd_result.returncode,
                }
            except subprocess.TimeoutExpired:
                return {"error": f"Primary command timed out after {command_timeout} seconds"}
            except Exception as e:
                return {"error": f"Primary command execution failed: {str(e)}"}
            if write_target_file is not None and write_file_content is not None:
                try:
                    path = os.path.abspath(os.path.expanduser(write_target_file))
                    if not isinstance(write_file_content, str):
                        return {"error": "write_file_content must be a string"}
                    if len(write_file_content.encode("utf-8")) > MAX_FILE_BYTES:
                        return {
                            "error": f"Content too large ({len(write_file_content)} bytes). "
                                     f"Max allowed is {MAX_FILE_BYTES} bytes for writing."
                        }
                    mode = write_file_mode.lower()
                    if mode not in ["overwrite", "append"]:
                        return {"error": "write_file_mode must be 'overwrite' or 'append'"}
                    parent_dir = os.path.dirname(path)
                    if parent_dir and not os.path.exists(parent_dir):
                        if ".." in parent_dir:
                            return {"error": "Directory traversal not allowed for writing"}
                        os.makedirs(parent_dir, exist_ok=True)
                    file_mode_char = "w" if mode == "overwrite" else "a"
                    with open(path, file_mode_char, encoding="utf-8") as f:
                        written = f.write(write_file_content)
                    results["operations"]["write_file"] = {
                        "success": True,
                        "path": path,
                        "mode": mode,
                        "bytes_written": written,
                    }
                except PermissionError:
                    return {"error": f"Permission denied to write file: {path}"}
                except Exception as e:
                    return {"error": f"Failed to write file: {str(e)}"}
            if read_target_file is not None:
                try:
                    path = os.path.abspath(os.path.expanduser(read_target_file))
                    if not os.path.exists(path):
                        return {"error": f"File does not exist: {path}"}
                    if not os.path.isfile(path):
                        return {"error": f"Path is not a file: {path}"}
                    file_size = os.path.getsize(path)
                    if file_size > MAX_FILE_BYTES:
                        return {
                            "error": f"File too large ({file_size} bytes). "
                                     f"Max allowed is {MAX_FILE_BYTES} bytes for reading."
                        }
                    content = ""
                    with open(path, "r", encoding="utf-8") as f:
                        if read_file_start_line is not None or read_file_end_line is not None:
                            if read_file_start_line is not None and read_file_start_line < 1:
                                return {"error": "read_file_start_line must be >= 1"}
                            if read_file_end_line is not None and read_file_end_line < 1:
                                return {"error": "read_file_end_line must be >= 1"}
                            lines = f.readlines()
                            start = (read_file_start_line - 1) if read_file_start_line else 0
                            end = read_file_end_line if read_file_end_line else len(lines)
                            if start >= len(lines):
                                return {"error": "read_file_start_line beyond file length"}
                            if end < start:
                                return {"error": "read_file_end_line must be >= read_file_start_line"}
                            content = "".join(lines[start:end])
                        else:
                            content = f.read()
                    results["operations"]["read_file"] = {
                        "success": True,
                        "path": path,
                        "size": len(content),
                        "content": content,
                    }
                except UnicodeDecodeError:
                    return {"error": f"File is not UTF-8 text: {path}"}
                except PermissionError:
                    return {"error": f"Permission denied to read file: {path}"}
                except Exception as e:
                    return {"error": f"Failed to read file: {str(e)}"}
            if list_target_directory is not None:
                try:
                    path = os.path.abspath(os.path.expanduser(list_target_directory))
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
                    results["operations"]["list_directory"] = {
                        "success": True,
                        "path": path,
                        "count": len(detailed_items),
                        "items": detailed_items,
                    }
                except PermissionError:
                    return {"error": f"Permission denied to list directory: {path}"}
                except Exception as e:
                    return {"error": f"Failed to list directory: {str(e)}"}
            if second_command is not None:
                try:
                    parts = shlex.split(second_command)
                    if not parts:
                        return {"error": "Empty second command"}
                    cmd_name = parts[0]
                    if cmd_name not in ALLOWED_COMMANDS:
                        return {
                            "error": f"Second command '{cmd_name}' is not allowed.",
                            "allowed": ALLOWED_COMMANDS,
                        }
                    cmd_result = subprocess.run(
                        parts,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=second_command_timeout,
                    )
                    results["operations"]["second_command_execution"] = {
                        "success": True,
                        "command": second_command,
                        "stdout": cmd_result.stdout,
                        "stderr": cmd_result.stderr,
                        "returncode": cmd_result.returncode,
                    }
                except subprocess.TimeoutExpired:
                    return {"error": f"Second command timed out after {second_command_timeout} seconds"}
                except Exception as e:
                    return {"error": f"Second command execution failed: {str(e)}"}
            results["success"] = True
            results["message"] = "Chained operations completed successfully."
            return results
        except Exception as e:
            return {"error": f"An unexpected error occurred during chained operations: {str(e)}"}