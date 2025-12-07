import os
import subprocess
import shlex
from typing import Optional, Dict, Any, List
def register(server):
    @server.tool()
    def write_file_meta(
        path: str,
        content: str,
        mode: str = "overwrite",
        max_bytes: int = 200_000,  # Max bytes for primary write, also reused for read_file
        execute_command_str: Optional[str] = None,
        execute_command_timeout: int = 10,
        list_directory_path: Optional[str] = None,
        read_file_path: Optional[str] = None,
        read_file_start_line: Optional[int] = None,
        read_file_end_line: Optional[int] = None,
        additional_write_file_path: Optional[str] = None,
        additional_write_file_content: Optional[str] = None,
        additional_write_file_mode: str = "overwrite",
    ) -> Dict[str, Any]:
        results: Dict[str, Any] = {
            "success": False,
            "filename": path,  # Main filename
            "operations_performed": {
                "main_write_file": {"status": "skipped", "error": "Not started yet"},
                "execute_command": {"status": "skipped"},
                "list_directory": {"status": "skipped"},
                "read_file": {"status": "skipped"},
                "additional_write_file": {"status": "skipped"},
            },
            "message": "Operation started."
        }
        try:
            main_write_path = os.path.abspath(os.path.expanduser(path))
            try:
                if not isinstance(content, str):
                    return {"error": "content must be a string for main_write_file"}
                if len(content.encode("utf-8")) > max_bytes:
                    return {
                        "error": f"Content too large ({len(content)} bytes) for main_write_file. "
                                 f"Max allowed is {max_bytes} bytes."
                    }
                _mode = mode.lower()
                if _mode not in ["overwrite", "append"]:
                    return {"error": "mode must be 'overwrite' or 'append' for main_write_file"}
                parent_dir = os.path.dirname(main_write_path)
                if parent_dir and not os.path.exists(parent_dir):
                    if ".." in parent_dir:  # Basic traversal prevention
                        return {"error": "Directory traversal not allowed for main_write_file parent"}
                    os.makedirs(parent_dir, exist_ok=True)
                file_mode_char = "w" if _mode == "overwrite" else "a"
                with open(main_write_path, file_mode_char, encoding="utf-8") as f:
                    written_bytes = f.write(content)
                results["operations_performed"]["main_write_file"] = {
                    "status": "success",
                    "path": main_write_path,
                    "mode": _mode,
                    "bytes_written": written_bytes,
                    "message": f"Wrote {written_bytes} bytes to {main_write_path} ({_mode})"
                }
                results["message"] = f"Mandatory file written: {main_write_path}. "
            except PermissionError:
                return {"error": f"Permission denied for main_write_file: {main_write_path}"}
            except Exception as e:
                return {"error": f"Failed mandatory write_file operation: {str(e)}"}
            if execute_command_str is not None:
                try:
                    allowed_commands = ["ls", "pwd", "whoami", "echo", "date"]
                    parts = shlex.split(execute_command_str)
                    if not parts:
                        return {"error": "Empty command provided for execute_command"}
                    cmd = parts[0]
                    if cmd not in allowed_commands:
                        return {
                            "error": f"Command '{cmd}' is not allowed for execute_command.",
                            "allowed": allowed_commands
                        }
                    cmd_result = subprocess.run(
                        parts,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=execute_command_timeout
                    )
                    results["operations_performed"]["execute_command"] = {
                        "status": "success",
                        "command": execute_command_str,
                        "stdout": cmd_result.stdout,
                        "stderr": cmd_result.stderr,
                        "returncode": cmd_result.returncode,
                        "message": f"Command '{cmd}' executed safely"
                    }
                    results["message"] += "Command executed. "
                except subprocess.TimeoutExpired:
                    results["operations_performed"]["execute_command"] = {
                        "status": "error",
                        "error": f"Command timed out after {execute_command_timeout} seconds"
                    }
                except Exception as e:
                    results["operations_performed"]["execute_command"] = {
                        "status": "error",
                        "error": f"Execution failed for execute_command: {str(e)}"
                    }
            if list_directory_path is not None:
                try:
                    list_dir_abs_path = os.path.abspath(os.path.expanduser(list_directory_path))
                    if not os.path.exists(list_dir_abs_path):
                        return {"error": f"Path does not exist for list_directory: {list_dir_abs_path}"}
                    if not os.path.isdir(list_dir_abs_path):
                        return {"error": f"Path is not a directory for list_directory: {list_dir_abs_path}"}
                    items: List[Dict[str, Any]] = []
                    for item_name in os.listdir(list_dir_abs_path):
                        item_path = os.path.join(list_dir_abs_path, item_name)
                        items.append({
                            "name": item_name,
                            "type": "directory" if os.path.isdir(item_path) else "file",
                            "absolute_path": os.path.abspath(item_path),
                            "is_symlink": os.path.islink(item_path)
                        })
                    results["operations_performed"]["list_directory"] = {
                        "status": "success",
                        "path": list_dir_abs_path,
                        "count": len(items),
                        "items": items,
                        "message": f"Listed {len(items)} items in {list_dir_abs_path}"
                    }
                    results["message"] += "Directory listed. "
                except PermissionError:
                    results["operations_performed"]["list_directory"] = {
                        "status": "error",
                        "error": f"Permission denied for list_directory: {list_dir_abs_path}"
                    }
                except Exception as e:
                    results["operations_performed"]["list_directory"] = {
                        "status": "error",
                        "error": f"Error listing directory: {str(e)}"
                    }
            if read_file_path is not None:
                try:
                    read_file_abs_path = os.path.abspath(os.path.expanduser(read_file_path))
                    if not os.path.exists(read_file_abs_path):
                        return {"error": f"File does not exist for read_file: {read_file_abs_path}"}
                    if not os.path.isfile(read_file_abs_path):
                        return {"error": f"Path is not a file for read_file: {read_file_abs_path}"}
                    file_size = os.path.getsize(read_file_abs_path)
                    if file_size > max_bytes:
                        return {
                            "error": f"File too large ({file_size} bytes) for read_file. "
                                     f"Max allowed is {max_bytes} bytes."
                        }
                    with open(read_file_abs_path, "r", encoding="utf-8") as f:
                        file_content_segment = ""
                        if read_file_start_line is not None or read_file_end_line is not None:
                            if read_file_start_line is not None and read_file_start_line < 1:
                                return {"error": "read_file_start_line must be >= 1"}
                            if read_file_end_line is not None and read_file_end_line < 1:
                                return {"error": "read_file_end_line must be >= 1"}
                            lines = f.readlines()
                            start = (read_file_start_line - 1) if read_file_start_line else 0
                            end = read_file_end_line if read_file_end_line else len(lines)
                            if start >= len(lines) and len(lines) > 0:
                                return {"error": "read_file_start_line beyond file length"}
                            if end < start:
                                return {"error": "read_file_end_line must be >= read_file_start_line"}
                            file_content_segment = "".join(lines[start:end])
                        else:
                            file_content_segment = f.read()
                    results["operations_performed"]["read_file"] = {
                        "status": "success",
                        "path": read_file_abs_path,
                        "size": len(file_content_segment),
                        "content": file_content_segment,
                        "message": f"Read {len(file_content_segment)} bytes from {read_file_abs_path}"
                    }
                    results["message"] += "File read. "
                except UnicodeDecodeError:
                    results["operations_performed"]["read_file"] = {
                        "status": "error",
                        "error": f"File is not UTF-8 text for read_file: {read_file_abs_path}"
                    }
                except PermissionError:
                    results["operations_performed"]["read_file"] = {
                        "status": "error",
                        "error": f"Permission denied for read_file: {read_file_abs_path}"
                    }
                except Exception as e:
                    results["operations_performed"]["read_file"] = {
                        "status": "error",
                        "error": f"Error reading file: {str(e)}"
                    }
            if additional_write_file_path is not None and additional_write_file_content is not None:
                try:
                    add_write_path = os.path.abspath(os.path.expanduser(additional_write_file_path))
                    if not isinstance(additional_write_file_content, str):
                        return {"error": "additional_write_file_content must be a string"}
                    if len(additional_write_file_content.encode("utf-8")) > max_bytes:
                        return {
                            "error": f"Content too large ({len(additional_write_file_content)} bytes) "
                                     f"for additional_write_file. Max allowed is {max_bytes} bytes."
                        }
                    _add_mode = additional_write_file_mode.lower()
                    if _add_mode not in ["overwrite", "append"]:
                        return {"error": "additional_write_file_mode must be 'overwrite' or 'append'"}
                    add_parent_dir = os.path.dirname(add_write_path)
                    if add_parent_dir and not os.path.exists(add_parent_dir):
                        if ".." in add_parent_dir:
                            return {"error": "Directory traversal not allowed for additional_write_file parent"}
                        os.makedirs(add_parent_dir, exist_ok=True)
                    add_file_mode_char = "w" if _add_mode == "overwrite" else "a"
                    with open(add_write_path, add_file_mode_char, encoding="utf-8") as f:
                        add_written_bytes = f.write(additional_write_file_content)
                    results["operations_performed"]["additional_write_file"] = {
                        "status": "success",
                        "path": add_write_path,
                        "mode": _add_mode,
                        "bytes_written": add_written_bytes,
                        "message": f"Wrote {add_written_bytes} bytes to {add_write_path} ({_add_mode})"
                    }
                    results["message"] += "Additional file written. "
                except PermissionError:
                    results["operations_performed"]["additional_write_file"] = {
                        "status": "error",
                        "error": f"Permission denied for additional_write_file: {add_write_path}"
                    }
                except Exception as e:
                    results["operations_performed"]["additional_write_file"] = {
                        "status": "error",
                        "error": f"Failed additional write_file operation: {str(e)}"
                    }
            results["success"] = True
            return results
        except Exception as e:
            return {"error": f"An unexpected error occurred in write_file_meta: {str(e)}"}
