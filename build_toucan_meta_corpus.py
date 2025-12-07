import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from datasets import load_dataset
def canonicalize_tool_name(raw: str) -> str:
    if not isinstance(raw, str):
        return ""
    parts = raw.split("-")
    if len(parts) <= 1:
        return raw
    return parts[-1]
def get_mcp_server_id(full_name: str) -> Optional[str]:
    if not isinstance(full_name, str) or "-" not in full_name:
        return None
    parts = full_name.split("-")
    if len(parts) <= 1:
        return None
    return "-".join(parts[:-1])
def parse_messages_field(field: Any) -> List[Dict[str, Any]]:
    if isinstance(field, list):
        return field
    if isinstance(field, dict) and "messages" in field:
        inner = field["messages"]
        if isinstance(inner, list):
            return inner
    if isinstance(field, str):
        try:
            parsed = json.loads(field)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            return []
    return []
def extract_full_tool_sequence(messages: List[Dict[str, Any]]) -> List[str]:
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
def extract_tool_specs_from_system_message(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not messages:
        return []
    system_msg = messages[0]
    content = system_msg.get("content", "")
    if not isinstance(content, str) or "tool_declare" not in content:
        return []
    start_idx = content.find("tool_declare")
    if start_idx == -1:
        return []
    start_bracket = content.find("[", start_idx)
    if start_bracket == -1:
        return []
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
def extract_quality_scores(row: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    q_score = None
    r_score = None
    for key, val in row.items():
        if key.startswith("question_quality_assessment_") and isinstance(val, dict):
            q_score = val.get("overall_score", q_score)
        if key.startswith("response_quality_assessment_") and isinstance(val, dict):
            r_score = val.get("overall_score", r_score)
    return q_score, r_score
def extract_metadata_servers(metadata_raw: Any) -> Any:
    if not isinstance(metadata_raw, str):
        return None
    try:
        md = json.loads(metadata_raw)
    except json.JSONDecodeError:
        return None
    return md.get("servers") or md.get("mcp_servers")
def load_patterns(pattern_path: str, max_patterns: Optional[int] = None) -> List[Dict[str, Any]]:
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
    records.sort(key=lambda x: x["support"], reverse=True)
    if max_patterns is not None:
        records = records[:max_patterns]
    return records
def sequence_contains_pattern(
    seq: List[str],
    pattern: List[str],
    contiguous: bool = True,
) -> bool:
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
        it = iter(seq)
        return all(p in it for p in pattern)
def update_tool_schemas_from_specs(
    tool_schemas: Dict[str, Dict[str, Any]],
    tool_specs: List[Dict[str, Any]],
) -> None:
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
def main():
    DATASET_NAME = "Agent-Ark/Toucan-1.5M"
    CONFIG_NAME = "Kimi-K2"      # good for tool calls
    MAX_ROWS = 5000              # you can increase if your machine can handle it
    PATTERN_PATH = "toucan_patterns.json"
    MAX_PATTERNS_FOR_JOIN = 500  # join only top-K patterns to keep size reasonable
    CONTIGUOUS_PATTERNS = True   # set False to allow gaps when matching patterns
    OUTPUT_TRACES = "toucan_traces.jsonl"
    OUTPUT_PATTERN_OCC = "toucan_pattern_occurrences.jsonl"
    OUTPUT_TOOL_SCHEMAS = "toucan_tool_schemas.json"
    print(f"\n🔵 Loading Toucan-1.5M (config={CONFIG_NAME})...")
    ds = load_dataset(DATASET_NAME, CONFIG_NAME, split="train")
    total_rows = len(ds)
    print(f"Total rows available: {total_rows}")
    if MAX_ROWS and MAX_ROWS < total_rows:
        ds = ds.select(range(MAX_ROWS))
        print(f"Subsampled to {len(ds)} rows.\n")
    rows: List[Dict[str, Any]] = [dict(ex) for ex in ds]
    print(f"🔵 Loading patterns from {PATTERN_PATH} ...")
    patterns = load_patterns(PATTERN_PATH, max_patterns=MAX_PATTERNS_FOR_JOIN)
    print(f"Loaded {len(patterns)} patterns for join.\n")
    traces_fp = open(OUTPUT_TRACES, "w", encoding="utf-8")
    patt_occ_fp = open(OUTPUT_PATTERN_OCC, "w", encoding="utf-8")
    tool_schemas: Dict[str, Dict[str, Any]] = {}
    print("🔵 Processing rows and building meta-corpus...")
    for idx, row in enumerate(rows):
        uuid = row.get("uuid")
        subset = row.get("subset") or row.get("subset_name")
        question = row.get("question")
        metadata_raw = row.get("metadata")
        messages = parse_messages_field(row.get("messages"))
        full_seq = extract_full_tool_sequence(messages)
        canon_seq = extract_canonical_sequence(full_seq)
        mcp_servers = sorted(
            {
                s
                for s in (get_mcp_server_id(name) for name in full_seq)
                if s is not None
            }
        )
        target_tools_raw = row.get("target_tools") or ""
        if isinstance(target_tools_raw, str):
            target_tools_list = [
                canonicalize_tool_name(t.strip())
                for t in target_tools_raw.split(",")
                if t.strip()
            ]
        else:
            target_tools_list = []
        q_score, r_score = extract_quality_scores(row)
        metadata_servers = extract_metadata_servers(metadata_raw)
        tool_specs = extract_tool_specs_from_system_message(messages)
        if tool_specs:
            update_tool_schemas_from_specs(tool_schemas, tool_specs)
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
