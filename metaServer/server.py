import sys
import os
import importlib.util
from pathlib import Path
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("Error: mcp package not found. Install with: pip install 'mcp[cli]'", file=sys.stderr)
    sys.exit(1)
mcp = FastMCP("meta-tools", json_response=True)
def load_tools(tools_dir: str = "tools"):
    tools_path = Path(__file__).parent / tools_dir
    if not tools_path.exists():
        print(f"Warning: Tools directory '{tools_dir}' not found", file=sys.stderr)
        return
    for tool_file in tools_path.glob("*.py"):
        if tool_file.name.startswith("_"):
            continue  # Skip private/internal files
        module_name = tool_file.stem
        try:
            spec = importlib.util.spec_from_file_location(module_name, tool_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "register"):
                module.register(mcp)
                print(f"Loaded tool: {module_name}", file=sys.stderr)
            else:
                print(f"Warning: {module_name} has no register() function", file=sys.stderr)
        except Exception as e:
            print(f"Error loading tool {module_name}: {e}", file=sys.stderr)
if __name__ == "__main__":
    load_tools()
    mcp.run(transport="stdio")
