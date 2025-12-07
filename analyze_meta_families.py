import json
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict, List
CANDIDATES_PATH = Path(
    "/Users/kanishk/Documents/Advanced NLP/Final_Project/MetaAgent/meta_tool_candidates.jsonl"
)
FAMILIES_OUT_PATH = Path(
    "/Users/kanishk/Documents/Advanced NLP/Final_Project/MetaAgent/meta_families.json"
)
def load_candidates(path: Path) -> List[Dict[str, Any]]:
    patterns: List[Dict[str, Any]] = []
    if not path.exists():
        raise FileNotFoundError(f"Candidates file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[WARN] Skipping invalid JSON on line {i}: {e}")
                continue
            pattern_info = obj.get("pattern", {})
            seq = pattern_info.get("sequence")
            if not isinstance(seq, list) or not seq:
                continue
            support = pattern_info.get("support", 1)
            length = pattern_info.get("length", len(seq))
            patterns.append({
                "meta_tool_id": obj.get("meta_tool_id"),
                "tool_name": obj.get("tool_name"),
                "description": obj.get("description"),
                "sequence": seq,
                "support": int(support),
                "length": int(length),
                "raw": obj,  # keep the full original if you need it later
            })
    patterns.sort(key=lambda x: x.get("support", 0), reverse=True)
    print(f"[INFO] Loaded {len(patterns)} patterns from {path}")
    return patterns
def build_start_tool_families(patterns: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for p in patterns:
        seq = p["sequence"]
        first_tool = seq[0]
        buckets[first_tool].append(p)
    families: Dict[str, Dict[str, Any]] = {}
    for first_tool, fam_patterns in buckets.items():
        optional_tools_set = set()
        total_support = 0
        for p in fam_patterns:
            total_support += int(p.get("support", 0))
            seq = p["sequence"]
            for t in seq[1:]:
                optional_tools_set.add(t)
        families[first_tool] = {
            "first_tool": first_tool,
            "patterns": fam_patterns,
            "all_optional_tools": sorted(list(optional_tools_set)),
            "total_support": total_support,
        }
    return families
def print_family_summary(families: Dict[str, Dict[str, Any]]) -> None:
    print("\n========== META TOOL FAMILY SUMMARY ==========")
    print(f"Total families (potential meta tools): {len(families)}\n")
    sorted_fams = sorted(
        families.values(),
        key=lambda fam: fam["total_support"],
        reverse=True,
    )
    for fam in sorted_fams:
        first_tool = fam["first_tool"]
        num_patterns = len(fam["patterns"])
        total_support = fam["total_support"]
        optional_tools = fam["all_optional_tools"]
        example_entries = []
        for p in fam["patterns"][:3]:
            example_entries.append({
                "meta_tool_id": p["meta_tool_id"],
                "tool_name": p["tool_name"],
                "sequence": p["sequence"],
                "support": p["support"],
            })
        print(f"Family starting with: {first_tool}")
        print(f"  #patterns      : {num_patterns}")
        print(f"  total support  : {total_support}")
        print(f"  optional tools : {optional_tools if optional_tools else '[]'}")
        print(f"  examples       : {example_entries}")
        print("-" * 60)
def save_families_json(families: Dict[str, Dict[str, Any]], out_path: Path) -> None:
    serializable = {}
    for first_tool, fam in families.items():
        serializable[first_tool] = {
            "first_tool": fam["first_tool"],
            "total_support": fam["total_support"],
            "all_optional_tools": fam["all_optional_tools"],
            "patterns": fam["patterns"],  # includes meta_tool_id, tool_name, sequence, support, etc.
        }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)
    print(f"[INFO] Saved families summary to {out_path}")
def main():
    patterns = load_candidates(CANDIDATES_PATH)
    families = build_start_tool_families(patterns)
    print_family_summary(families)
    save_families_json(families, FAMILIES_OUT_PATH)
if __name__ == "__main__":
    main()
