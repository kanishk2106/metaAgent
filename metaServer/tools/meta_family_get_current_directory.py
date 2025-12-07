import os
import subprocess
import shlex
from typing import Optional, Dict, Any, List, Union
def register(server):
    @server.tool()
    def get_current_directory_meta(
        change_directory_to: Optional[str] = None,
        execute_command_str: Optional[str] = None,
        execute_command_timeout: int = 10,
        list_directory_path: Optional[str] = None,
        read_file_path: Optional[str] = None,
        read_file_start_line: Optional[int] = None,
        read_file_end_line: Optional[int] = None,
        read_file_max_bytes: int = 200_000,
        write_file_path: Optional[str] = None,
        write_file_content: Optional[str] = None,
        write_file_mode: str = "overwrite",
        write_file_max_bytes: int = 200_000,
    ) -> Dict[str, Any]:
        operations = {}
        overall_message_parts = []
        initial_cwd = None
        try:
            try:
                initial_cwd = os.getcwd()
                operations["initial_current_directory"] = {
                    "success": True,
                    "current_directory": initial_cwd,
                    "absolute_path": os.path.abspath(initial_cwd),
                }
                overall_message_parts.append(f"Initial CWD: {initial_cwd}")
            except Exception as e:
                return {"error": f"Failed to get initial current directory: {str(e)}"}
            if change_directory_to is not None:
                try:
                    target_path = os.path.abspath(change_directory_to)
                    if not os.path.exists(target_path):
                        return {"error": f"Change directory failed: Path does not exist: {change_directory_to}"}
                    if not os.path.isdir(target_path):
                        return {"error": f"Change directory failed: Path is not a directory: {change_directory_to}"}
                    old_cwd_before_change = os.getcwd()
                    os.chdir(target_path)
                    operations["change_directory"] = {
                        "success": True,
                        "previous_directory": old_cwd_before_change,
                        "current_directory": os.getcwd(),
                    }
                    overall_message_parts.append(f"Changed directory to {os.getcwd()}")
                except PermissionError:
                    return {"error": f"Change directory failed: Permission denied: {change_directory_to}"}
                except Exception as e:
                    return {"error": f"Change directory failed: {str(e)}"}
            if execute_command_str is not None:
                allowed_commands = ["ls", "pwd", "whoami", "echo", "date"]
                cmd_result = None
                try:
                    parts = shlex.split(execute_command_str)
                    if not parts:
                        return {"error": "Execute command failed: Empty command string"}
                    cmd = parts[0]
                    if cmd not in allowed_commands:
                        return {
                            "error": f"Execute command failed: Command '{cmd}' is not allowed.",
                            "allowed_commands": allowed_commands
                        }
                    result = subprocess.run(
                        parts,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=execute_command_timeout
                    )
                    cmd_result = {
                        "success": True,
                        "command": execute_command_str,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "returncode": result.returncode,
                    }
                    operations["execute_command"] = cmd_result
                    overall_message_parts.append(f"Executed command '{cmd}'")
                except subprocess.TimeoutExpired:
                    return {"error": f"Execute command failed: Command timed out after {execute_command_timeout} seconds"}
                except Exception as e:
                    return {"error": f"Execute command failed: {str(e)}"}
            if list_directory_path is not None:
                list_dir_abs_path = os.path.abspath(os.path.expanduser(list_directory_path))
                list_dir_results = None
                try:
                    if not os.path.exists(list_dir_abs_path):
                        return {"error": f"List directory failed: Path does not exist: {list_directory_path}"}
                    if not os.path.isdir(list_dir_abs_path):
                        return {"error": f"List directory failed: Path is not a directory: {list_directory_path}"}
                    items = os.listdir(list_dir_abs_path)
                    detailed_items = []
                    for item in items:
                        item_path = os.path.join(list_dir_abs_path, item)
                        is_dir = os.path.isdir(item_path)
                        is_link = os.path.islink(item_path)
                        detailed_items.append({
                            "name": item,
                            "type": "directory" if is_dir else "file",
                            "absolute_path": os.path.abspath(item_path),
                            "is_symlink": is_link
                        })
                    list_dir_results = {
                        "success": True,
                        "path": list_dir_abs_path,
                        "count": len(detailed_items),
                        "items": detailed_items,
                    }
                    operations["list_directory"] = list_dir_results
                    overall_message_parts.append(f"Listed {list_dir_results['count']} items in {list_directory_path}")
                except PermissionError:
                    return {"error": f"List directory failed: Permission denied: {list_directory_path}"}
                except Exception as e:
                    return {"error": f"List directory failed: {str(e)}"}
            if read_file_path is not None:
                read_file_abs_path = os.path.abspath(os.path.expanduser(read_file_path))
                read_file_results = None
                try:
                    if not os.path.exists(read_file_abs_path):
                        return {"error": f"Read file failed: File does not exist: {read_file_path}"}
                    if not os.path.isfile(read_file_abs_path):
                        return {"error": f"Read file failed: Path is not a file: {read_file_path}"}
                    file_size = os.path.getsize(read_file_abs_path)
                    if file_size > read_file_max_bytes:
                        return {
                            "error": f"Read file failed: File too large ({file_size} bytes). Max allowed is {read_file_max_bytes} bytes.",
                            "file_path": read_file_path
                        }
                    with open(read_file_abs_path, "r", encoding="utf-8") as f:
                        content = ""
                        if read_file_start_line is not None or read_file_end_line is not None:
                            if read_file_start_line is not None and read_file_start_line < 1:
                                return {"error": "Read file failed: start_line must be >= 1"}
                            if read_file_end_line is not None and read_file_end_line < 1:
                                return {"error": "Read file failed: end_line must be >= 1"}
                            lines = f.readlines()
                            start = (read_file_start_line - 1) if read_file_start_line else 0
                            end = read_file_end_line if read_file_end_line else len(lines)
                            if start >= len(lines) and len(lines) > 0:
                                return {"error": "Read file failed: start_line beyond file length"}
                            if end < start:
                                return {"error": "Read file failed: end_line must be >= start_line"}
                            content = "".join(lines[start:end])
                        else:
                            content = f.read()
                    read_file_results = {
                        "success": True,
                        "path": read_file_abs_path,
                        "size": len(content.encode('utf-8')), # Bytes not chars
                        "content": content,
                    }
                    operations["read_file"] = read_file_results
                    overall_message_parts.append(f"Read {read_file_results['size']} bytes from {read_file_path}")
                except UnicodeDecodeError:
                    return {"error": f"Read file failed: File is not UTF-8 text: {read_file_path}"}
                except PermissionError:
                    return {"error": f"Read file failed: Permission denied: {read_file_path}"}
                except Exception as e:
                    return {"error": f"Read file failed: {str(e)}"}
            if write_file_path is not None and write_file_content is not None:
                write_file_abs_path = os.path.abspath(os.path.expanduser(write_file_path))
                write_file_results = None
                try:
                    if not isinstance(write_file_content, str):
                        return {"error": "Write file failed: content must be a string"}
                    if len(write_file_content.encode("utf-8")) > write_file_max_bytes:
                        return {
                            "error": f"Write file failed: Content too large ({len(write_file_content.encode('utf-8'))} bytes). Max allowed is {write_file_max_bytes} bytes."
                        }
                    mode = write_file_mode.lower()
                    if mode not in ["overwrite", "append"]:
                        return {"error": "Write file failed: mode must be 'overwrite' or 'append'"}
                    parent_dir = os.path.dirname(write_file_abs_path)
                    if parent_dir and not os.path.exists(parent_dir):
                        if ".." in parent_dir:
                            return {"error": "Write file failed: Directory traversal not allowed in parent path creation"}
                        os.makedirs(parent_dir, exist_ok=True)
                    file_mode_flag = "w" if mode == "overwrite" else "a"
                    with open(write_file_abs_path, file_mode_flag, encoding="utf-8") as f:
                        written_bytes = f.write(write_file_content)
                    write_file_results = {
                        "success": True,
                        "path": write_file_abs_path,
                        "mode": mode,
                        "bytes_written": written_bytes,
                    }
                    operations["write_file"] = write_file_results
                    overall_message_parts.append(f"Wrote {written_bytes} bytes to {write_file_path} ({mode})")
                except PermissionError:
                    return {"error": f"Write file failed: Permission denied: {write_file_path}"}
                except Exception as e:
                    return {"error": f"Write file failed: {str(e)}"}
            final_message = "Operations completed: " + "; ".join(overall_message_parts)
            return {
                "success": True,
                "overall_message": final_message,
                "current_directory_at_end": os.getcwd(), # Get CWD one last time
                "operations": operations,
            }
        except Exception as e:
            return {"error": f"An unexpected error occurred during filesystem management: {str(e)}"}