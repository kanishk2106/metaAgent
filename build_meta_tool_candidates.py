import json
from typing import List, Dict, Any, Optional
LOCAL_TOOLS = {
    "create_document",
    "add_heading",
    "add_paragraph",
    "add_table",
    "format_table",
    "list_directory",
    "read_file",
    "write_file",
    "get_current_directory",
    "change_directory",
    "execute_command",
}
def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
def load_jsonl(path: str):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows
def load_patterns(path: str, min_len=2):
    data = load_json(path)
    data = [p for p in data if len(p["pattern"]) >= min_len]
    clean = []
    for p in data:
        seq = p["pattern"]
        if len(set(seq)) == 1:
            continue
        clean.append(p)
    clean.sort(key=lambda x: x["support"], reverse=True)
    return clean  # Return ALL patterns
def is_local_safe(meta: Dict[str, Any]) -> bool:
    seq = meta["pattern"]["sequence"]
    return all(tool in LOCAL_TOOLS for tool in seq)
def extract_creator_args_from_param_schemas(tool_schema: Dict[str, Any]) -> Dict[str, str]:
    params = tool_schema.get("parameter_schemas", [])
    if not params:
        return {}
    schema = params[0]
    props = schema.get("properties", {})
    out = {}
    for k, v in props.items():
        if isinstance(v, dict) and "type" in v:
            out[k] = v["type"]
        else:
            out[k] = "string"
    return out
def normalize_input_sources(call):
    src = call.get("input_sources")
    if isinstance(src, dict):
        out = {}
        for k, v in src.items():
            if isinstance(v, list):
                out[k] = v
            else:
                out[k] = [v]
        return out
    return {}
def find_wiring(pattern, flow_chains):
    wiring = []
    for i in range(len(pattern) - 1):
        from_tool = pattern[i]
        to_tool = pattern[i + 1]
        for chain in flow_chains:
            seq = chain.get("tool_sequence_canonical", [])
            calls = chain.get("calls", [])
            for j in range(len(seq) - 1):
                if seq[j] == from_tool and seq[j + 1] == to_tool:
                    if j + 1 >= len(calls):
                        continue
                    call = calls[j + 1]
                    input_sources = normalize_input_sources(call)
                    for to_field, src_list in input_sources.items():
                        for src in src_list:
                            if "." not in src:
                                continue
                            parts = src.split(".", 1)
                            idx_str = parts[0]
                            field = parts[1]
                            try:
                                source_idx = int(idx_str)
                            except ValueError:
                                continue
                            if source_idx == j:
                                wiring.append({
                                    "from_tool": from_tool,
                                    "from_field": field,
                                    "to_tool": to_tool,
                                    "to_field": to_field
                                })
    uniq, seen = [], set()
    for w in wiring:
        key = (w["from_tool"], w["from_field"], w["to_tool"], w["to_field"])
        if key not in seen:
            seen.add(key)
            uniq.append(w)
    return uniq
def infer_output_schema_from_output(output_obj: Any) -> Dict[str, str]:
    if not output_obj:
        return {"result": "string"}
    if not isinstance(output_obj, dict):
        return {"result": "string"}
    out = {}
    for k, v in output_obj.items():
        if isinstance(v, str):
            out[k] = "string"
        elif isinstance(v, bool):
            out[k] = "boolean"
        elif isinstance(v, int) or isinstance(v, float):
            out[k] = "number"
        elif isinstance(v, list):
            out[k] = "array"
        elif isinstance(v, dict):
            out[k] = "object"
        else:
            out[k] = "string"
    if not out:
        return {"result": "string"}
    return out
def extract_example_and_output_args(pattern, flow_chains):
    for chain in flow_chains:
        seq = chain.get("tool_sequence_canonical", [])
        calls = chain.get("calls", [])
        if len(seq) < len(pattern):
            continue
        for i in range(len(seq) - len(pattern) + 1):
            if seq[i:i + len(pattern)] == pattern:
                window = calls[i:i + len(pattern)]
                if not window:
                    continue
                input_args = window[0].get("arguments", {}) or {}
                raw_out = window[-1].get("output", {}) or {}
                if raw_out is None or raw_out == {}:
                    raw_out = {"result": None}
                steps = []
                for c in window:
                    out = c.get("output", {}) or {"result": None}
                    steps.append({
                        "tool": c.get("tool_canonical"),
                        "arguments": c.get("arguments", {}),
                        "output": out
                    })
                inferred_output_args = infer_output_schema_from_output(raw_out)
                example = {
                    "input": input_args,
                    "steps": steps,
                    "output": raw_out
                }
                return example, inferred_output_args
    return None, {"result": "string"}
def build_meta_tool(meta_tool_id, pattern, support, schemas, wiring, example, output_args):
    name = "_".join(pattern)
    desc = f"A meta-tool that combines: {' → '.join(pattern)}"
    first_schema = schemas.get(pattern[0], {})
    input_args = extract_creator_args_from_param_schemas(first_schema)
    internal_steps = []
    for tool in pattern:
        internal_steps.append({
            "tool": tool,
            "schema": schemas.get(tool, {})
        })
    return {
        "meta_tool_id": meta_tool_id,
        "tool_name": name,
        "description": desc,
        "pattern": {
            "sequence": pattern,
            "support": support,
            "length": len(pattern)
        },
        "internal_steps": internal_steps,
        "wiring": wiring,
        "schema": {
            "input_args": input_args,
            "output_args": output_args
        },
        "examples": [example] if example else []
    }
def main():
    P_PAT = "toucan_patterns.json"
    P_SCH = "toucan_tool_schemas.json"
    P_FLOW = "tool_flow_chains.jsonl"
    OUT = "meta_tool_candidates.jsonl"
    print("\n🔵 Loading data...")
    patterns = load_patterns(P_PAT, min_len=2)  # Load ALL patterns
    print(f"  - Loaded {len(patterns)} non-trivial patterns (all patterns, no limit)")
    schemas = load_json(P_SCH)
    print(f"  - Loaded {len(schemas)} tool schemas")
    flows = load_jsonl(P_FLOW)
    print(f"  - Loaded {len(flows)} flow chain records")
    print("\n🔵 Building meta-tools from ALL patterns...")
    results = []
    for idx, p in enumerate(patterns):
        pattern = p["pattern"]
        support = p["support"]
        meta_id = f"mt_{idx + 1:04d}"
        wiring = find_wiring(pattern, flows)
        example, output_args = extract_example_and_output_args(pattern, flows)
        meta = build_meta_tool(
            meta_tool_id=meta_id,
            pattern=pattern,
            support=support,
            schemas=schemas,
            wiring=wiring,
            example=example,
            output_args=output_args
        )
        results.append(meta)
        if (idx + 1) % 100 == 0:
            print(f"  - Processed {idx + 1} / {len(patterns)} patterns")
    print(f"  - Total patterns processed: {len(patterns)}")
    print("\n🔵 Filtering for local-safe meta-tools...")
    print(f"  - Local-safe tool whitelist: {sorted(LOCAL_TOOLS)}")
    local_safe_results = [m for m in results if is_local_safe(m)]
    print(f"  - Total meta-tools: {len(results)}")
    print(f"  - Local-safe meta-tools: {len(local_safe_results)}")
    print(f"  - Filtered out: {len(results) - len(local_safe_results)}")
    results = local_safe_results
    print(f"\n🔵 Writing {len(results)} local-safe meta-tools to {OUT}...")
    with open(OUT, "w", encoding="utf-8") as f:
        for m in results:
            f.write(json.dumps(m) + "\n")
    print(f"\n✅ Done! Wrote {len(results)} local-safe meta-tool candidates to {OUT}")
    print("\n📊 Summary Statistics:")
    print(f"  - Total patterns mined: {len(patterns)}")
    print(f"  - Local-safe meta-tools: {len(results)}")
    print(f"  - Coverage: {len(results) / len(patterns) * 100:.1f}%")
    length_dist = {}
    for m in results:
        length = m["pattern"]["length"]
        length_dist[length] = length_dist.get(length, 0) + 1
    print("\n  Pattern length distribution:")
    for length in sorted(length_dist.keys()):
        print(f"    - Length {length}: {length_dist[length]} meta-tools")
    print("\n  Top 10 local-safe meta-tools by support:")
    top_10 = sorted(results, key=lambda x: x["pattern"]["support"], reverse=True)[:10]
    for i, m in enumerate(top_10, 1):
        seq = m["pattern"]["sequence"]
        support = m["pattern"]["support"]
        print(f"    {i:2d}. {' → '.join(seq[:3])}{'...' if len(seq) > 3 else ''} (support={support})")
    print()
if __name__ == "__main__":
    main()
