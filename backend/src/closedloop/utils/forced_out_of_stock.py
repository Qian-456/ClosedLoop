from __future__ import annotations


def parse_forced_out_of_stock_ids(raw: str) -> set[str]:
    if not raw:
        return set()

    s = str(raw).strip()
    if not s:
        return set()

    if (s.startswith("(") and s.endswith(")")) or (s.startswith("[") and s.endswith("]")):
        s = s[1:-1].strip()

    parts = [p.strip().strip("'").strip('"') for p in s.split(",")]
    return {p for p in parts if p}

