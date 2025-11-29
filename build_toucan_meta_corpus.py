# build_toucan_meta_corpus.py
# ---------------------------------------------------------
# Build a meta-tool corpus from Toucan-1.5M
#
# Inputs:
#   - HF dataset: Agent-Ark/Toucan-1.5M (config=Kimi-K2)
#   - toucan_patterns.json  (from your PrefixSpan mining step)
#
# Outputs:
#   1) toucan_traces.jsonl
#        One line per trajectory with:
#          - uuid, subset, question
#          - canonical tool sequence
#          - full MCP tool names
#          - inferred MCP servers
#          - target_tools (canonical)
#          - question/response quality scores
#
#   2) toucan_pattern_occurrences.jsonl
#        One line per (pattern, trajectory) match:
#          - pattern_id, pattern, pattern_support
#          - uuid, subset, question
#          - tool_sequence, tool_sequence_full
#          - mcp_servers, target_tools
#          - question/response quality
#
#   3) toucan_tool_schemas.json
#        Aggregated MCP tool schemas:
#          - canonical_name
#          - full MCP names seen
#          - server ids
#          - descriptions
#          - example parameter schemas
#
# This gives you *all the extra information* needed for
# Phase 2 meta-tool synthesis: consistent MCP tools,
# arguments, servers, and quality signals.
# ---------------------------------------------------------

import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from datasets import load_dataset


# -----------------------------
# Basic helpers
# -----------------------------
def canonicalize_tool_name(raw: str) -> str:
    """
    Reduce long MCP tool names into a canonical function name.

    Example:
        "blockscout-mcp-server-get_address_by_ens_name"
        -> "get_address_by_ens_name"
    """
    if not isinstance(raw, str):
        return ""
    parts = raw.split("-")
    if len(parts) <= 1:
        return raw
    return parts[-1]


def get_mcp_server_id(full_name: str) -> Optional[str]:
    """
    Infer MCP server id from the full tool name.

    Example:
        "blockscout-mcp-server-get_address_by_ens_name"
        -> "blockscout-mcp-server"
    """
    if not isinstance(full_name, str) or "-" not in full_name:
        return None
    parts = full_name.split("-")
    if len(parts) <= 1:
        return None
    return "-".join(parts[:-1])


# -----------------------------
# Parse Toucan messages safely
# -----------------------------
def parse_messages_field(field: Any) -> List[Dict[str, Any]]:
    """
    Toucan's 'messages' column (per paper) can be:

      - A JSON string of a list of messages
      - Already a Python list of dicts (datasets auto-parsed)
      - Rarely, a dict with nested 'messages'

    We normalize to: List[Dict].
    """
    # Already a list of messages?
    if isinstance(field, list):
        return field

    # Wrapped in dict
    if isinstance(field, dict) and "messages" in field:
        inner = field["messages"]
        if isinstance(inner, list):
            return inner

    # JSON string
    if isinstance(field, str):
        try:
            parsed = json.loads(field)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            return []

    return []


# -----------------------------
# Extract tool call sequences
# -----------------------------
def extract_full_tool_sequence(messages: List[Dict[str, Any]]) -> List[str]:
    """
    Extract the *full MCP tool names* from assistant messages with function_call.

    Messages look like (per paper):

      {
        "role": "assistant",
        "content": "",
        "function_call": {
          "name": "blockscout-mcp-server-get_address_by_ens_name",
          "arguments": "{...}"
        }
      }
    """
    seq: List[str] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "assistant":
            continue

        fc = msg.get("function_call")
        if isinstance(fc, dict):
            name = fc.get("name")
            if isinstance(name, str) and name:
                seq.append(name)

    return seq


def extract_canonical_sequence(full_seq: List[str]) -> List[str]:
    return [canonicalize_tool_name(t) for t in full_seq if t]


# -----------------------------
# Extract tool specs from system message
# -----------------------------
def extract_tool_specs_from_system_message(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Toucan (Appendix A) puts the MCP tool list in the system message content,
    often with a prefix like:

        "<|im_system|>tool_declare<|im_middle|>[{...tool specs...}]"

    This function:
      - Finds the JSON array after 'tool_declare'
      - Parses it into a list of tool specs
    """
    if not messages:
        return []

    system_msg = messages[0]
    content = system_msg.get("content", "")
    if not isinstance(content, str) or "tool_declare" not in content:
        return []

    # Find the first '[' after 'tool_declare'
    start_idx = content.find("tool_declare")
    if start_idx == -1:
        return []

    start_bracket = content.find("[", start_idx)
    if start_bracket == -1:
        return []

    # Bracket matching to find the closing ']'
    depth = 0
    end_bracket = None
    for i, ch in enumerate(content[start_bracket:], start=start_bracket):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end_bracket = i + 1
                break

    if end_bracket is None:
        return []

    json_blob = content[start_bracket:end_bracket]
    try:
        tools = json.loads(json_blob)
        if isinstance(tools, list):
            return tools
    except json.JSONDecodeError:
        return []

    return []


# -----------------------------
# Question / response quality
# -----------------------------
def extract_quality_scores(row: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    """
    Per paper, Toucan has:
      - question_quality_assessment_<model> : dict with 'overall_score'
      - response_quality_assessment_<model> : dict with 'overall_score'

    There may be multiple models; we just take the first one we find.
    """
    q_score = None
    r_score = None

    for key, val in row.items():
        if key.startswith("question_quality_assessment_") and isinstance(val, dict):
            q_score = val.get("overall_score", q_score)
        if key.startswith("response_quality_assessment_") and isinstance(val, dict):
            r_score = val.get("overall_score", r_score)

    return q_score, r_score


# -----------------------------
# Metadata helpers
# -----------------------------
def extract_metadata_servers(metadata_raw: Any) -> Any:
    """
    'metadata' is a JSON string that (per paper) contains:
      - original MCP server data
      - LLM annotations about servers/tools

    We try to parse it and return whatever is under 'servers' or 'mcp_servers'
    if present. If not, return None.
    """
    if not isinstance(metadata_raw, str):
        return None
    try:
        md = json.loads(metadata_raw)
    except json.JSONDecodeError:
        return None

    return md.get("servers") or md.get("mcp_servers")


# -----------------------------
# Pattern utilities
# -----------------------------
def load_patterns(pattern_path: str, max_patterns: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Load patterns from toucan_patterns.json (from your PrefixSpan script).

    Each entry is like:
        {"pattern": [...], "support": int}
    We attach a pattern_id and optionally keep only top-K by support.
    """
    with open(pattern_path, "r", encoding="utf-8") as f:
        arr = json.load(f)

    records = []
    for idx, item in enumerate(arr):
        records.append(
            {
                "id": idx,
                "pattern": item["pattern"],
                "support": int(item["support"]),
            }
        )

    # Sort by support desc
    records.sort(key=lambda x: x["support"], reverse=True)

    if max_patterns is not None:
        records = records[:max_patterns]

    return records


def sequence_contains_pattern(
    seq: List[str],
    pattern: List[str],
    contiguous: bool = True,
) -> bool:
    """
    Check if 'pattern' occurs in 'seq'.

    - If contiguous=True, we require a contiguous subsequence.
    - If contiguous=False, we allow gaps (subsequence).
    """
    if not pattern:
        return False

    n = len(seq)
    m = len(pattern)

    if m > n:
        return False

    if contiguous:
        for i in range(n - m + 1):
            if seq[i : i + m] == pattern:
                return True
        return False
    else:
        # non-contiguous subsequence
        it = iter(seq)
        return all(p in it for p in pattern)


# -----------------------------
# Tool schema accumulator
# -----------------------------
def update_tool_schemas_from_specs(
    tool_schemas: Dict[str, Dict[str, Any]],
    tool_specs: List[Dict[str, Any]],
) -> None:
    """
    Accumulate tool schema information into 'tool_schemas' dict.

    Each spec is roughly:
      {
        "type": "function",
        "function": {
          "name": "...",
          "description": "...",
          "parameters": {...}
        }
      }
    """
    for spec in tool_specs:
        fn = spec.get("function")
        if not isinstance(fn, dict):
            continue

        full_name = fn.get("name")
        if not isinstance(full_name, str) or not full_name:
            continue

        canonical = canonicalize_tool_name(full_name)
        server_id = get_mcp_server_id(full_name)
        desc = fn.get("description")
        params = fn.get("parameters")

        entry = tool_schemas.setdefault(
            canonical,
            {
                "canonical_name": canonical,
                "full_names": set(),
                "servers": set(),
                "descriptions": set(),
                "parameter_schemas": [],
            },
        )

        entry["full_names"].add(full_name)
        if server_id:
            entry["servers"].add(server_id)
        if isinstance(desc, str) and desc:
            entry["descriptions"].add(desc)
        if isinstance(params, dict) and params not in entry["parameter_schemas"]:
            entry["parameter_schemas"].append(params)


def finalize_tool_schemas(tool_schemas: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convert sets to lists and make the object JSON-serializable.
    """
    finalized = {}
    for k, v in tool_schemas.items():
        finalized[k] = {
            "canonical_name": v["canonical_name"],
            "full_names": sorted(v["full_names"]),
            "servers": sorted(v["servers"]),
            "descriptions": sorted(v["descriptions"]),
            "parameter_schemas": v["parameter_schemas"],
        }
    return finalized


# -----------------------------
# Main pipeline
# -----------------------------
def main():
    # -----------------------
    # Config
    # -----------------------
    DATASET_NAME = "Agent-Ark/Toucan-1.5M"
    CONFIG_NAME = "Kimi-K2"      # good for tool calls
    MAX_ROWS = 5000              # you can increase if your machine can handle it
    PATTERN_PATH = "toucan_patterns.json"
    MAX_PATTERNS_FOR_JOIN = 500  # join only top-K patterns to keep size reasonable
    CONTIGUOUS_PATTERNS = True   # set False to allow gaps when matching patterns

    OUTPUT_TRACES = "toucan_traces.jsonl"
    OUTPUT_PATTERN_OCC = "toucan_pattern_occurrences.jsonl"
    OUTPUT_TOOL_SCHEMAS = "toucan_tool_schemas.json"

    # -----------------------
    # Load dataset
    # -----------------------
    print(f"\n🔵 Loading Toucan-1.5M (config={CONFIG_NAME})...")
    ds = load_dataset(DATASET_NAME, CONFIG_NAME, split="train")
    total_rows = len(ds)
    print(f"Total rows available: {total_rows}")

    if MAX_ROWS and MAX_ROWS < total_rows:
        ds = ds.select(range(MAX_ROWS))
        print(f"Subsampled to {len(ds)} rows.\n")

    rows: List[Dict[str, Any]] = [dict(ex) for ex in ds]

    # -----------------------
    # Load mined patterns
    # -----------------------
    print(f"🔵 Loading patterns from {PATTERN_PATH} ...")
    patterns = load_patterns(PATTERN_PATH, max_patterns=MAX_PATTERNS_FOR_JOIN)
    print(f"Loaded {len(patterns)} patterns for join.\n")

    # -----------------------
    # Prepare outputs
    # -----------------------
    traces_fp = open(OUTPUT_TRACES, "w", encoding="utf-8")
    patt_occ_fp = open(OUTPUT_PATTERN_OCC, "w", encoding="utf-8")

    tool_schemas: Dict[str, Dict[str, Any]] = {}

    # -----------------------
    # Iterate rows
    # -----------------------
    print("🔵 Processing rows and building meta-corpus...")

    for idx, row in enumerate(rows):
        uuid = row.get("uuid")
        subset = row.get("subset") or row.get("subset_name")
        question = row.get("question")
        metadata_raw = row.get("metadata")

        # Parse messages
        messages = parse_messages_field(row.get("messages"))

        # Full and canonical tool sequences
        full_seq = extract_full_tool_sequence(messages)
        canon_seq = extract_canonical_sequence(full_seq)

        # Inferred MCP servers from tool names
        mcp_servers = sorted(
            {
                s
                for s in (get_mcp_server_id(name) for name in full_seq)
                if s is not None
            }
        )

        # Target tools (seed MCP tools used to generate question)
        target_tools_raw = row.get("target_tools") or ""
        if isinstance(target_tools_raw, str):
            target_tools_list = [
                canonicalize_tool_name(t.strip())
                for t in target_tools_raw.split(",")
                if t.strip()
            ]
        else:
            target_tools_list = []

        # Quality scores
        q_score, r_score = extract_quality_scores(row)

        # Metadata servers (if present)
        metadata_servers = extract_metadata_servers(metadata_raw)

        # Tool specs from system message (for schema aggregation)
        tool_specs = extract_tool_specs_from_system_message(messages)
        if tool_specs:
            update_tool_schemas_from_specs(tool_schemas, tool_specs)

        # --------- Write trace-level record ----------
        trace_record = {
            "uuid": uuid,
            "subset": subset,
            "question": question,
            "tool_sequence": canon_seq,
            "tool_sequence_full": full_seq,
            "mcp_servers": mcp_servers,
            "target_tools": target_tools_list,
            "question_quality_overall": q_score,
            "response_quality_overall": r_score,
            "metadata_servers": metadata_servers,
        }
        traces_fp.write(json.dumps(trace_record) + "\n")

        # --------- Pattern occurrences ----------
        if canon_seq:
            for patt in patterns:
                pattern_seq = patt["pattern"]
                if sequence_contains_pattern(
                    canon_seq,
                    pattern_seq,
                    contiguous=CONTIGUOUS_PATTERNS,
                ):
                    occ_record = {
                        "pattern_id": patt["id"],
                        "pattern": patt["pattern"],
                        "pattern_support": patt["support"],
                        "uuid": uuid,
                        "subset": subset,
                        "question": question,
                        "tool_sequence": canon_seq,
                        "tool_sequence_full": full_seq,
                        "mcp_servers": mcp_servers,
                        "target_tools": target_tools_list,
                        "question_quality_overall": q_score,
                        "response_quality_overall": r_score,
                    }
                    patt_occ_fp.write(json.dumps(occ_record) + "\n")

        if (idx + 1) % 500 == 0:
            print(f"  Processed {idx + 1} / {len(rows)} rows...")

    traces_fp.close()
    patt_occ_fp.close()

    # -----------------------
    # Finalize and save tool schemas
    # -----------------------
    print("\n🔵 Finalizing tool schemas...")
    finalized_schemas = finalize_tool_schemas(tool_schemas)
    with open(OUTPUT_TOOL_SCHEMAS, "w", encoding="utf-8") as f:
        json.dump(finalized_schemas, f, indent=2)

    print("\n✅ Done.")
    print(f"  - Traces written to: {OUTPUT_TRACES}")
    print(f"  - Pattern occurrences written to: {OUTPUT_PATTERN_OCC}")
    print(f"  - Tool schemas written to: {OUTPUT_TOOL_SCHEMAS}\n")


if __name__ == "__main__":
    main()
