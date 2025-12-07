import os
import subprocess
import shlex
from typing import Optional, Dict, Any, List, Union
def register(server):
    @server.tool()
    def list_directory_and_actions(
        path: str = ".",
        get_current_directory_before_actions: bool = False,
        get_current_directory_after_all_actions: bool = False,
        change_to_path: Optional[str] = None,
        command_to_execute: Optional[str] = None,
        command_timeout: int = 10,
        file_to_write_path: Optional[str] = None,
        file_content_to_write: Optional[str] = None,
        write_mode: str = "overwrite",
        write_max_bytes: int = 200_000,
        file_to_read_path: Optional[str] = None,
        read_start_line: Optional[int] = None,
        read_end_line: Optional[int] = None,
        read_max_bytes: int = 200_000,
        additional_list_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        operations_log: Dict[str, Any] = {
            "initial_directory_on_call": os.getcwd(),
            "get_current_directory_before_actions": None,
            "change_directory": None,
            "execute_command": None,
            "write_file": None,
            "read_file": None,
            "mandatory_list_directory": None,
            "additional_list_directory": None,
            "get_current_directory_after_all_actions": None,
        }
        try:
            if get_current_directory_before_actions:
                try:
                    operations_log["get_current_directory_before_actions"] = {
                        "success": True,
                        "current_directory": os.getcwd(),
                        "message": "Current directory retrieved before actions."
                    }
                except Exception as e:
                    operations_log["get_current_directory_before_actions"] = {"error": f"Failed to get CWD before actions: {str(e)}"}
            if change_to_path is not None:
                try:
                    abs_change_path = os.path.abspath(change_to_path)
                    if not os.path.exists(abs_change_path):
                        operations_log["change_directory"] = {"error": f"Path does not exist: {change_to_path}"}
                    elif not os.path.isdir(abs_change_path):
                        operations_log["change_directory"] = {"error": f"Path is not a directory: {change_to_path}"}
                    else:
                        old_cwd = os.getcwd()
                        os.chdir(abs_change_path)
                        operations_log["change_directory"] = {
                            "success": True,
                            "previous_directory": old_cwd,
                            "current_directory": os.getcwd(),
                            "message": f"Changed directory to {os.getcwd()}"
                        }
                except PermissionError:
                    operations_log["change_directory"] = {"error": f"Permission denied to change to: {change_to_path}"}
                except Exception as e:
                    operations_log["change_directory"] = {"error": f"Failed to change directory: {str(e)}"}
            if command_to_execute is not None:
                allowed_commands = ["ls", "pwd", "whoami", "echo", "date"] # Whitelist from base tool
                try:
                    parts = shlex.split(command_to_execute)
                    if not parts:
                        operations_log["execute_command"] = {"error": "Empty command string provided."}
                    elif parts[0] not in allowed_commands:
                        operations_log["execute_command"] = {
                            "error": f"Command '{parts[0]}' is not allowed.",
                            "allowed": allowed_commands
                        }
                    else:
                        result = subprocess.run(
                            parts,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            timeout=command_timeout
                        )
                        operations_log["execute_command"] = {
                            "success": True,
                            "command": command_to_execute,
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                            "returncode": result.returncode,
                            "message": f"Command '{parts[0]}' executed."
                        }
                except subprocess.TimeoutExpired:
                    operations_log["execute_command"] = {"error": f"Command timed out after {command_timeout} seconds"}
                except Exception as e:
                    operations_log["execute_command"] = {"error": f"Execution failed: {str(e)}"}
            if file_to_write_path is not None:
                if file_content_to_write is None:
                    operations_log["write_file"] = {"error": "file_content_to_write is required when file_to_write_path is provided."}
                else:
                    try:
                        abs_write_path = os.path.abspath(os.path.expanduser(file_to_write_path))
                        if not isinstance(file_content_to_write, str):
                            operations_log["write_file"] = {"error": "file_content_to_write must be a string"}
                        elif len(file_content_to_write.encode("utf-8")) > write_max_bytes:
                            operations_log["write_file"] = {
                                "error": f"Content too large ({len(file_content_to_write)} bytes). "
                                         f"Max allowed is {write_max_bytes} bytes."
                            }
                        else:
                            write_mode_norm = write_mode.lower()
                            if write_mode_norm not in ["overwrite", "append"]:
                                operations_log["write_file"] = {"error": "write_mode must be 'overwrite' or 'append'"}
                            else:
                                parent_dir = os.path.dirname(abs_write_path)
                                if parent_dir and not os.path.exists(parent_dir):
                                    if ".." in parent_dir: # Basic check for directory traversal
                                        operations_log["write_file"] = {"error": "Directory traversal not allowed in parent path creation."}
                                    else:
                                        os.makedirs(parent_dir, exist_ok=True)
                                file_open_mode = "w" if write_mode_norm == "overwrite" else "a"
                                with open(abs_write_path, file_open_mode, encoding="utf-8") as f:
                                    written_bytes = f.write(file_content_to_write)
                                operations_log["write_file"] = {
                                    "success": True,
                                    "path": abs_write_path,
                                    "mode": write_mode_norm,
                                    "bytes_written": written_bytes,
                                    "message": f"Wrote {written_bytes} bytes to {abs_write_path} ({write_mode_norm})"
                                }
                    except PermissionError:
                        operations_log["write_file"] = {"error": f"Permission denied to write to: {file_to_write_path}"}
                    except Exception as e:
                        operations_log["write_file"] = {"error": f"Failed to write file: {str(e)}"}
            if file_to_read_path is not None:
                try:
                    abs_read_path = os.path.abspath(os.path.expanduser(file_to_read_path))
                    if not os.path.exists(abs_read_path):
                        operations_log["read_file"] = {"error": f"File does not exist: {file_to_read_path}"}
                    elif not os.path.isfile(abs_read_path):
                        operations_log["read_file"] = {"error": f"Path is not a file: {file_to_read_path}"}
                    else:
                        file_size = os.path.getsize(abs_read_path)
                        if file_size > read_max_bytes:
                            operations_log["read_file"] = {
                                "error": f"File too large ({file_size} bytes). "
                                         f"Max allowed is {read_max_bytes} bytes."
                            }
                        else:
                            with open(abs_read_path, "r", encoding="utf-8") as f:
                                content = ""
                                if read_start_line is not None or read_end_line is not None:
                                    if read_start_line is not None and read_start_line < 1:
                                        operations_log["read_file"] = {"error": "read_start_line must be >= 1"}
                                    elif read_end_line is not None and read_end_line < 1:
                                        operations_log["read_file"] = {"error": "read_end_line must be >= 1"}
                                    else:
                                        lines = f.readlines()
                                        start = (read_start_line - 1) if read_start_line else 0
                                        end = read_end_line if read_end_line else len(lines)
                                        if start >= len(lines):
                                            operations_log["read_file"] = {"error": "read_start_line beyond file length"}
                                        elif end < start:
                                            operations_log["read_file"] = {"error": "read_end_line must be >= read_start_line"}
                                        else:
                                            content = "".join(lines[start:end])
                                            operations_log["read_file"] = {
                                                "success": True,
                                                "path": abs_read_path,
                                                "size": len(content),
                                                "content": content,
                                                "message": f"Read {len(content)} bytes (lines {read_start_line}-{read_end_line or 'EOF'}) from {abs_read_path}"
                                            }
                                else:
                                    content = f.read()
                                    operations_log["read_file"] = {
                                        "success": True,
                                        "path": abs_read_path,
                                        "size": len(content),
                                        "content": content,
                                        "message": f"Read {len(content)} bytes from {abs_read_path}"
                                    }
                except UnicodeDecodeError:
                    operations_log["read_file"] = {"error": f"File is not UTF-8 text: {file_to_read_path}"}
                except PermissionError:
                    operations_log["read_file"] = {"error": f"Permission denied to read: {file_to_read_path}"}
                except Exception as e:
                    operations_log["read_file"] = {"error": f"Failed to read file: {str(e)}"}
            abs_list_path = os.path.abspath(os.path.expanduser(path))
            if not os.path.exists(abs_list_path):
                return {"error": f"Mandatory list_directory path does not exist: {path}"}
            if not os.path.isdir(abs_list_path):
                return {"error": f"Mandatory list_directory path is not a directory: {path}"}
            try:
                items = os.listdir(abs_list_path)
                detailed_items: List[Dict[str, Union[str, bool]]] = []
                for item in items:
                    item_path = os.path.join(abs_list_path, item)
                    is_dir = os.path.isdir(item_path)
                    is_link = os.path.islink(item_path)
                    detailed_items.append({
                        "name": item,
                        "type": "directory" if is_dir else "file",
                        "absolute_path": os.path.abspath(item_path),
                        "is_symlink": is_link
                    })
                operations_log["mandatory_list_directory"] = {
                    "success": True,
                    "path": abs_list_path,
                    "count": len(detailed_items),
                    "items": detailed_items,
                    "message": f"Listed {len(detailed_items)} items in {abs_list_path}"
                }
            except PermissionError:
                return {"error": f"Permission denied for mandatory list_directory: {path}"}
            except Exception as e:
                return {"error": f"Error during mandatory list_directory: {str(e)}"}
            if additional_list_path is not None:
                abs_add_list_path = os.path.abspath(os.path.expanduser(additional_list_path))
                if not os.path.exists(abs_add_list_path):
                    operations_log["additional_list_directory"] = {"error": f"Additional list_directory path does not exist: {additional_list_path}"}
                elif not os.path.isdir(abs_add_list_path):
                    operations_log["additional_list_directory"] = {"error": f"Additional list_directory path is not a directory: {additional_list_path}"}
                else:
                    try:
                        items = os.listdir(abs_add_list_path)
                        detailed_items_add: List[Dict[str, Union[str, bool]]] = []
                        for item in items:
                            item_path = os.path.join(abs_add_list_path, item)
                            is_dir = os.path.isdir(item_path)
                            is_link = os.path.islink(item_path)
                            detailed_items_add.append({
                                "name": item,
                                "type": "directory" if is_dir else "file",
                                "absolute_path": os.path.abspath(item_path),
                                "is_symlink": is_link
                            })
                        operations_log["additional_list_directory"] = {
                            "success": True,
                            "path": abs_add_list_path,
                            "count": len(detailed_items_add),
                            "items": detailed_items_add,
                            "message": f"Listed {len(detailed_items_add)} items in {abs_add_list_path} (additional)"
                        }
                    except PermissionError:
                        operations_log["additional_list_directory"] = {"error": f"Permission denied for additional list_directory: {additional_list_path}"}
                    except Exception as e:
                        operations_log["additional_list_directory"] = {"error": f"Error during additional list_directory: {str(e)}"}
            if get_current_directory_after_all_actions:
                try:
                    operations_log["get_current_directory_after_all_actions"] = {
                        "success": True,
                        "current_directory": os.getcwd(),
                        "message": "Current directory retrieved after all actions."
                    }
                except Exception as e:
                    operations_log["get_current_directory_after_all_actions"] = {"error": f"Failed to get CWD after actions: {str(e)}"}
            overall_message = f"Mandatory listing of '{path}' completed."
            performed_optional_actions = [
                k for k, v in operations_log.items()
                if v is not None and v != operations_log["initial_directory_on_call"] and k not in ["mandatory_list_directory", "initial_directory_on_call"]
            ]
            if performed_optional_actions:
                overall_message += f" Optional actions performed: {', '.join(performed_optional_actions)}."
            return {
                "success": True,
                "overall_message": overall_message,
                "operations_summary": operations_log,
            }
        except Exception as e:
            return {"error": f"An unexpected error occurred during meta tool execution: {str(e)}"}