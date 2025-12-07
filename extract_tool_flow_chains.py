import json
from typing import Any, Dict, List, Optional, Tuple
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
def parse_json_maybe(s: Any) -> Tuple[Optional[Any], Optional[str]]:
    if not isinstance(s, str):
        return None, None
    txt = s.strip()
    if not txt:
        return None, txt
    if not (txt.startswith("{") or txt.startswith("[")):
        return None, txt
    try:
        parsed = json.loads(txt)
        return parsed, txt
    except json.JSONDecodeError:
        return None, txt
def extract_tool_calls_with_outputs(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    n = len(messages)
    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "assistant":
            continue
        fc = msg.get("function_call")
        if not isinstance(fc, dict):
            continue
        tool_full = fc.get("name")
        if not isinstance(tool_full, str) or not tool_full:
            continue
        raw_args = fc.get("arguments")
        parsed_args, raw_args_str = parse_json_maybe(raw_args)
        parsed_out = None
        raw_out_str = None
        for j in range(i + 1, min(i + 4, n)):
            msg2 = messages[j]
            if not isinstance(msg2, dict):
                continue
            role2 = msg2.get("role")
            if role2 not in ("assistant", "tool"):
                continue
            content2 = msg2.get("content")
            po, ro = parse_json_maybe(content2)
            if po is not None or ro is not None:
                parsed_out = po
                raw_out_str = ro
                break
        calls.append(
            {
                "index": len(calls),
                "tool_full": tool_full,
                "tool_canonical": canonicalize_tool_name(tool_full),
                "server": get_mcp_server_id(tool_full),
                "arguments": parsed_args,
                "raw_arguments": raw_args_str,
                "output": parsed_out,
                "raw_output": raw_out_str,
                "input_sources": {},
            }
        )
    return calls
def infer_input_sources(calls: List[Dict[str, Any]]) -> None:
    for k, call in enumerate(calls):
        args = call.get("arguments")
        if not isinstance(args, dict):
            continue
        input_sources: Dict[str, List[str]] = {}
        value_map: Dict[str, List[str]] = {}
        for i in range(k):
            prev = calls[i]
            out = prev.get("output")
            if isinstance(out, dict):
                for ok, ov in out.items():
                    v_str = str(ov)
                    value_map.setdefault(v_str, []).append(f"{i}.{ok}")
        for ak, av in args.items():
            v_str = str(av)
            if v_str in value_map:
                input_sources[ak] = value_map[v_str]
        call["input_sources"] = input_sources
def load_pattern_occurrences(path: str) -> Dict[str, Dict[str, Any]]:
    by_uuid: Dict[str, Dict[str, Any]] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            uuid = rec.get("uuid")
            if not uuid:
                continue
            entry = by_uuid.setdefault(
                uuid,
                {
                    "uuid": uuid,
                    "subset": rec.get("subset"),
                    "question": rec.get("question"),
                    "patterns": {},
                },
            )
            pid = rec.get("pattern_id")
            if pid is None:
                continue
            if pid not in entry["patterns"]:
                entry["patterns"][pid] = {
                    "pattern_id": pid,
                    "pattern": rec.get("pattern"),
                    "pattern_support": rec.get("pattern_support"),
                }
    for uuid, entry in by_uuid.items():
        entry["patterns"] = list(entry["patterns"].values())
    return by_uuid
def main():
    DATASET_NAME = "Agent-Ark/Toucan-1.5M"
    CONFIG_NAME = "Kimi-K2"
    MAX_ROWS = 5000  # should match build_toucan_meta_corpus.py
    PATTERN_OCC_PATH = "toucan_pattern_occurrences.jsonl"
    OUTPUT_FLOW_CHAINS = "tool_flow_chains.jsonl"
    print(f"\n🔵 Loading pattern occurrences from {PATTERN_OCC_PATH} ...")
    patterns_by_uuid = load_pattern_occurrences(PATTERN_OCC_PATH)
    print(f"Found {len(patterns_by_uuid)} uuids with matched patterns.\n")
    if not patterns_by_uuid:
        print("⚠️ No pattern occurrences found. Did you run build_toucan_meta_corpus.py?")
        return
    print(f"🔵 Loading Toucan-1.5M (config={CONFIG_NAME})...")
    ds = load_dataset(DATASET_NAME, CONFIG_NAME, split="train")
    total_rows = len(ds)
    print(f"Total rows available: {total_rows}")
    if MAX_ROWS and MAX_ROWS < total_rows:
        ds = ds.select(range(MAX_ROWS))
        print(f"Subsampled to {len(ds)} rows.\n")
    rows: List[Dict[str, Any]] = [dict(ex) for ex in ds]
    out_fp = open(OUTPUT_FLOW_CHAINS, "w", encoding="utf-8")
    print("🔵 Extracting tool flow chains for matching uuids...")
    processed = 0
    matched = 0
    for idx, row in enumerate(rows):
        processed += 1
        uuid = row.get("uuid")
        if not uuid or uuid not in patterns_by_uuid:
            continue
        meta = patterns_by_uuid[uuid]
        subset = meta.get("subset") or row.get("subset") or row.get("subset_name")
        question = meta.get("question") or row.get("question")
        messages = parse_messages_field(row.get("messages"))
        calls = extract_tool_calls_with_outputs(messages)
        if not calls:
            continue
        infer_input_sources(calls)
        record = {
            "uuid": uuid,
            "subset": subset,
            "question": question,
            "patterns": meta["patterns"],
            "tool_sequence_canonical": [c["tool_canonical"] for c in calls],
            "calls": calls,
        }
        out_fp.write(json.dumps(record) + "\n")
        matched += 1
        if (idx + 1) % 500 == 0:
            print(f"  Processed {idx + 1} rows, chains written for {matched} trajectories...")
    out_fp.close()
    print("\n✅ Done.")
    print(f"  - Processed rows: {processed}")
    print(f"  - Flow chains written for: {matched} trajectories")
    print(f"  - Output file: {OUTPUT_FLOW_CHAINS}\n")
if __name__ == "__main__":
    main()
