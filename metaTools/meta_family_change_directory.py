import os
import subprocess
import shlex
from typing import Optional, Dict, Any
def register(server):
    @server.tool()
    def change_directory_meta(
        target_directory: str,
        execute_command_text: Optional[str] = None,
        execute_command_timeout: int = 10,
        list_directory_path: Optional[str] = None, # If not None, list this path. If ".", list current.
        read_file_path: Optional[str] = None,
        read_file_start_line: Optional[int] = None,
        read_file_end_line: Optional[int] = None,
        read_file_max_bytes: int = 200_000,
        write_file_path: Optional[str] = None,
        write_file_content: Optional[str] = None,
        write_file_mode: str = "overwrite",
        write_file_max_bytes: int = 200_000,
    ) -> Dict[str, Any]:
        operations = {
            "cwd_change": {},
            "command_executed": None,
            "directory_listed": None,
            "file_read": None,
            "file_written": None,
        }
        overall_message_parts = []
        try:
            target_directory_abs = os.path.abspath(target_directory)
            if not os.path.exists(target_directory_abs):
                return {"error": f"Path does not exist: {target_directory}"}
            if not os.path.isdir(target_directory_abs):
                return {"error": f"Path is not a directory: {target_directory}"}
            old_cwd = os.getcwd()
            os.chdir(target_directory_abs)
            new_cwd = os.getcwd()
            operations["cwd_change"] = {
                "success": True,
                "previous_directory": old_cwd,
                "current_directory": new_cwd,
            }
            overall_message_parts.append(f"Changed directory to {new_cwd}")
            if execute_command_text is not None:
                allowed_commands = ["ls", "pwd", "whoami", "echo", "date"]
                cmd_result = {"success": False, "error": "Unknown error during command execution"}
                try:
                    parts = shlex.split(execute_command_text)
                    if not parts:
                        cmd_result["error"] = "Empty command for execution."
                        return {"error": cmd_result["error"]} # Fail early if command is invalid
                    cmd = parts[0]
                    if cmd not in allowed_commands:
                        cmd_result["error"] = f"Command '{cmd}' is not allowed for execution."
                        cmd_result["allowed"] = allowed_commands
                        return {"error": cmd_result["error"]} # Fail early if command not allowed
                    result = subprocess.run(
                        parts,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=execute_command_timeout
                    )
                    cmd_result = {
                        "success": True,
                        "command": execute_command_text,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "returncode": result.returncode,
                        "message": f"Command '{cmd}' executed safely"
                    }
                    overall_message_parts.append(f"Executed command '{execute_command_text}'")
                except subprocess.TimeoutExpired:
                    cmd_result["error"] = f"Command timed out after {execute_command_timeout} seconds"
                    return {"error": cmd_result["error"]}
                except Exception as e:
                    cmd_result["error"] = f"Execution failed for '{execute_command_text}': {str(e)}"
                    return {"error": cmd_result["error"]}
                finally:
                    operations["command_executed"] = cmd_result
            if list_directory_path is not None:
                list_result = {"success": False, "error": "Unknown error during directory listing"}
                try:
                    path_to_list = os.path.abspath(os.path.expanduser(list_directory_path))
                    if not os.path.exists(path_to_list):
                        return {"error": f"Path to list does not exist: {list_directory_path}"}
                    if not os.path.isdir(path_to_list):
                        return {"error": f"Path to list is not a directory: {list_directory_path}"}
                    items = os.listdir(path_to_list)
                    detailed_items = []
                    for item in items:
                        item_path = os.path.join(path_to_list, item)
                        is_dir = os.path.isdir(item_path)
                        is_link = os.path.islink(item_path)
                        detailed_items.append({
                            "name": item,
                            "type": "directory" if is_dir else "file",
                            "absolute_path": os.path.abspath(item_path),
                            "is_symlink": is_link
                        })
                    list_result = {
                        "success": True,
                        "path": path_to_list,
                        "count": len(detailed_items),
                        "items": detailed_items,
                        "message": f"Listed {len(detailed_items)} items in {path_to_list}"
                    }
                    overall_message_parts.append(f"Listed {len(detailed_items)} items in {path_to_list}")
                except PermissionError:
                    list_result["error"] = f"Permission denied for listing: {list_directory_path}"
                    return {"error": list_result["error"]}
                except Exception as e:
                    list_result["error"] = f"Error listing directory '{list_directory_path}': {str(e)}"
                    return {"error": list_result["error"]}
                finally:
                    operations["directory_listed"] = list_result
            if read_file_path is not None:
                read_result = {"success": False, "error": "Unknown error during file reading"}
                try:
                    path_to_read = os.path.abspath(os.path.expanduser(read_file_path))
                    if not os.path.exists(path_to_read):
                        return {"error": f"File to read does not exist: {read_file_path}"}
                    if not os.path.isfile(path_to_read):
                        return {"error": f"Path to read is not a file: {read_file_path}"}
                    file_size = os.path.getsize(path_to_read)
                    if file_size > read_file_max_bytes:
                        return {
                            "error": f"File too large ({file_size} bytes). "
                                     f"Max allowed for reading is {read_file_max_bytes} bytes."
                        }
                    with open(path_to_read, "r", encoding="utf-8") as f:
                        content = ""
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
                    read_result = {
                        "success": True,
                        "path": path_to_read,
                        "size": len(content),
                        "content": content,
                        "message": f"Read {len(content)} bytes from {path_to_read}"
                    }
                    overall_message_parts.append(f"Read {len(content)} bytes from {path_to_read}")
                except UnicodeDecodeError:
                    read_result["error"] = f"File is not UTF-8 text: {read_file_path}"
                    return {"error": read_result["error"]}
                except PermissionError:
                    read_result["error"] = f"Permission denied for reading: {read_file_path}"
                    return {"error": read_result["error"]}
                except Exception as e:
                    read_result["error"] = f"Error reading file '{read_file_path}': {str(e)}"
                    return {"error": read_result["error"]}
                finally:
                    operations["file_read"] = read_result
            if write_file_path is not None or write_file_content is not None:
                if write_file_path is None or write_file_content is None:
                    return {"error": "Both 'write_file_path' and 'write_file_content' must be provided for writing a file."}
                write_result = {"success": False, "error": "Unknown error during file writing"}
                try:
                    path_to_write = os.path.abspath(os.path.expanduser(write_file_path))
                    if not isinstance(write_file_content, str):
                        return {"error": "write_file_content must be a string"}
                    if len(write_file_content.encode("utf-8")) > write_file_max_bytes:
                        return {
                            "error": f"Content too large ({len(write_file_content)} bytes). "
                                     f"Max allowed for writing is {write_file_max_bytes} bytes."
                        }
                    mode = write_file_mode.lower()
                    if mode not in ["overwrite", "append"]:
                        return {"error": "write_file_mode must be 'overwrite' or 'append'"}
                    parent_dir = os.path.dirname(path_to_write)
                    if parent_dir and not os.path.exists(parent_dir):
                        if ".." in parent_dir:
                            return {"error": "Directory traversal not allowed for writing"}
                        os.makedirs(parent_dir, exist_ok=True)
                    file_mode = "w" if mode == "overwrite" else "a"
                    with open(path_to_write, file_mode, encoding="utf-8") as f:
                        written = f.write(write_file_content)
                    write_result = {
                        "success": True,
                        "path": path_to_write,
                        "mode": mode,
                        "bytes_written": written,
                        "message": f"Wrote {written} bytes to {path_to_write} ({mode})"
                    }
                    overall_message_parts.append(f"Wrote {written} bytes to {path_to_write}")
                except PermissionError:
                    write_result["error"] = f"Permission denied for writing: {write_file_path}"
                    return {"error": write_result["error"]}
                except Exception as e:
                    write_result["error"] = f"Error writing file '{write_file_path}': {str(e)}"
                    return {"error": write_result["error"]}
                finally:
                    operations["file_written"] = write_result
            final_message = ". ".join(overall_message_parts) + "."
            if not overall_message_parts: # This case should ideally not be hit, as CWD change is mandatory
                 final_message = "No operations performed beyond directory change."
            return {
                "success": True,
                "current_working_directory": new_cwd,
                "operations": operations,
                "message": final_message
            }
        except Exception as e:
            return {"error": f"An unexpected error occurred in change_directory_meta: {str(e)}"}