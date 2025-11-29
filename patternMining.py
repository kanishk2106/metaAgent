# mine_toucan_patterns.py
# ---------------------------------------------------------
# Step 1: Load Toucan (correct config with tool traces)
# Step 2: Extract tool-call sequences
# Step 3: Mine sequential patterns (PrefixSpan)
# Step 4: Save patterns for Phase 2
# ---------------------------------------------------------

import json
from typing import List, Dict, Any, Tuple
from datasets import load_dataset
from prefixspan import PrefixSpan


# ------------------------------------------------
# 1. Load Toucan with correct configuration
# ------------------------------------------------
def load_toucan_sample(config: str = "Kimi-K2", max_rows: int = 5000):
    """
    Loads a subset of Toucan-1.5M.
    Recommended configs for tool-traces:
        - "Kimi-K2"   (densest tool calls)
        - "OSS"
        - "Qwen3"
    SFT does NOT contain useful tool-call logs.
    """
    print(f"\n🔵 Loading Toucan-1.5M (config={config})...")
    ds = load_dataset("Agent-Ark/Toucan-1.5M", config, split="train")

    print(f"Total rows available: {len(ds)}")
    if max_rows and max_rows < len(ds):
        ds = ds.select(range(max_rows))
        print(f"Subsampled to {len(ds)} rows.\n")

    # Convert HF dataset objects to Python dicts
    return [dict(ex) for ex in ds]


# ------------------------------------------------
# 2. Extract tool-call sequence from messages
# ------------------------------------------------
def extract_tool_sequence(messages: List[Dict[str, Any]]) -> List[str]:
    """
    Extracts tool-call names from assistant messages
    containing: 'function_call': { name: ..., arguments: ... }
    """
    seq = []
    for msg in messages:
        if msg.get("role") == "assistant" and "function_call" in msg:
            fc = msg.get("function_call") or {}
            name = fc.get("name")
            if name:
                seq.append(name)
    return seq


# ------------------------------------------------
# 3. Canonicalize tool names (shorten long tool identifiers)
# ------------------------------------------------
def canonicalize_tool_name(raw: str) -> str:
    """
    Reduce long tool names for clean patterns.
    Example:
        "mcp-blockscout-get_transaction_by_hash"
        → "get_transaction_by_hash"
    """
    if "-" in raw:
        return raw.split("-")[-1]
    return raw


# ------------------------------------------------
# 4. Parse 'messages' from each Toucan row
# ------------------------------------------------
def parse_messages(field):
    """
    Handles several data formats:
      - JSON string containing a list
      - Direct Python list
      - Dictionary with nested 'messages'
    """
    # Already a list?
    if isinstance(field, list):
        return field

    # Wrapped in a dict?
    if isinstance(field, dict) and "messages" in field:
        return field["messages"]

    # JSON string?
    if isinstance(field, str):
        try:
            parsed = json.loads(field)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            return []

    return []


# ------------------------------------------------
# 5. Build sequences for all dataset rows
# ------------------------------------------------
def build_sequences(rows: List[Dict[str, Any]], canonical=True) -> List[List[str]]:
    sequences = []

    for ex in rows:
        raw = ex.get("messages") or ex.get("conversations")

        if raw is None:
            continue

        messages = parse_messages(raw)
        if not messages:
            continue

        seq_raw = extract_tool_sequence(messages)
        if not seq_raw:
            continue

        seq = [canonicalize_tool_name(t) for t in seq_raw] if canonical else seq_raw
        sequences.append(seq)

    print(f"\n🟢 Extracted {len(sequences)} tool sequences from {len(rows)} rows.")
    return sequences


# ------------------------------------------------
# 6. Run PrefixSpan sequential pattern mining
# ------------------------------------------------
def mine_patterns(sequences: List[List[str]], min_support=5, max_len=4):
    print("\n🔵 Running PrefixSpan mining...")

    if not sequences:
        print("⚠️ No sequences available — cannot mine patterns.")
        return []

    ps = PrefixSpan(sequences)
    ps.minlen = 2
    ps.maxlen = max_len

    raw = ps.frequent(min_support)  # returns (support, pattern)
    patterns = [(pattern, support) for support, pattern in raw]

    patterns.sort(key=lambda x: x[1], reverse=True)

    print(f"🟢 Found {len(patterns)} frequent patterns.\n")
    return patterns


# ------------------------------------------------
# 7. Save patterns to JSON file
# ------------------------------------------------
def save_patterns(patterns, out_path="toucan_patterns.json"):
    packed = [{"pattern": p, "support": s} for p, s in patterns]
    with open(out_path, "w") as f:
        json.dump(packed, f, indent=2)
    print(f"💾 Saved patterns to {out_path}\n")


# ------------------------------------------------
# MAIN
# ------------------------------------------------
def main():
    # Best starting config for tool calls
    rows = load_toucan_sample(config="Kimi-K2", max_rows=5000)

    # Debug: print sample row structure
    print("Sample row:")
    print(json.dumps(rows[0], indent=2)[:2000], "\n")

    sequences = build_sequences(rows, canonical=True)

    patterns = mine_patterns(
        sequences,
        min_support=5,     # lowered support for more patterns
        max_len=4
    )

    print("🔶 Top 20 Patterns:")
    for i, (pattern, support) in enumerate(patterns[:20], 1):
        print(f"{i:2d}. {pattern}  (support={support})")

    save_patterns(patterns, "toucan_patterns.json")


if __name__ == "__main__":
    main()
