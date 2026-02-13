#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]

IGNORE_DIRS = {
    ".git", ".github", ".venv", "venv", "__pycache__", "node_modules", "dist", "build",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "target"
}

PY_METRIC_DEF = re.compile(
    r"""\b(?:Counter|Gauge|Histogram|Summary)\s*\(\s*["'](?P<name>[^"']+)["']""",
    re.MULTILINE,
)

PY_LABELNAMES = re.compile(
    r"""labelnames\s*=\s*(?P<lst>\[[^\]]*\]|\([^\)]*\))""",
    re.MULTILINE,
)

PY_POS_LABELS = re.compile(
    r"""\b(?:Counter|Gauge|Histogram|Summary)\s*\(\s*["'][^"']+["']\s*,\s*["'][^"']*["']\s*,\s*(?P<lst>\[[^\]]*\]|\([^\)]*\))""",
    re.MULTILINE,
)

RUST_METRIC_NAME = re.compile(
    r"""["'](?P<name>atr_[a-z0-9_]+)["']""",
    re.MULTILINE,
)

RUST_LABELS = re.compile(
    r"""\&\s*\[\s*(?P<lst>(?:(?:"[^"]+")|(?:'[^']+'))\s*(?:,\s*(?:(?:"[^"]+")|(?:'[^']+'))\s*)*)\]""",
    re.MULTILINE,
)

STR_IN_LIST = re.compile(r"""["']([^"']+)["']""")


def iter_source_files(root: Path) -> List[Path]:
    out: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fn in filenames:
            if fn.endswith(".py") or fn.endswith(".rs"):
                out.append(Path(dirpath) / fn)
    return out


def parse_labels_from_list_literal(lst: str) -> List[str]:
    return STR_IN_LIST.findall(lst)


def extract_from_python(text: str) -> List[Tuple[str, List[str], str]]:
    """Returns list of (metric_name, labels, kind) where kind in {Counter,Gauge,Histogram,Summary}"""
    results: List[Tuple[str, List[str], str]] = []
    # crude: find each metric name, then try to find nearest labelnames in the same constructor
    for m in PY_METRIC_DEF.finditer(text):
        name = m.group("name")
        # slice forward a bit to capture constructor args
        tail = text[m.start(): m.start() + 600]
        kind = re.findall(r"\b(Counter|Gauge|Histogram|Summary)\b", tail)
        kind = kind[0] if kind else "Unknown"

        labels: List[str] = []
        m_kw = PY_LABELNAMES.search(tail)
        if m_kw:
            labels = parse_labels_from_list_literal(m_kw.group("lst"))
        else:
            m_pos = PY_POS_LABELS.search(tail)
            if m_pos:
                labels = parse_labels_from_list_literal(m_pos.group("lst"))

        results.append((name, labels, kind))
    return results


def extract_from_rust(text: str) -> List[Tuple[str, List[str], str]]:
    """
    Best-effort extraction:
    - metrics names: string literals starting with 'atr_'
    - labels: &["shard","reason"] patterns near metrics usage/registration
    """
    results: List[Tuple[str, List[str], str]] = []
    # Find name occurrences
    for m in RUST_METRIC_NAME.finditer(text):
        name = m.group("name")
        # take local window to guess labels
        window = text[max(0, m.start() - 300): m.start() + 600]
        labels: List[str] = []
        m_labels = RUST_LABELS.search(window)
        if m_labels:
            labels = parse_labels_from_list_literal("[" + m_labels.group("lst") + "]")
        results.append((name, labels, "RustMetric"))
    return results


def load_contract(path: Path) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    contract_path = REPO_ROOT / "monitoring" / "metrics_contract.json"
    if not contract_path.exists():
        print(f"[FAIL] Missing contract file: {contract_path}")
        return 2

    contract = load_contract(contract_path)
    allowed_metrics: Set[str] = set(contract["allowed_metrics"])
    allowed_label_keys: Set[str] = set(contract["allowed_label_keys"])
    forbidden_label_keys: Set[str] = set(contract.get("forbidden_label_keys", []))
    counter_suffixes: List[str] = contract.get("counter_must_end_with", ["_total"])

    files = iter_source_files(REPO_ROOT)
    found: List[Tuple[str, List[str], str, str]] = []  # (name, labels, kind, file)

    for fp in files:
        txt = fp.read_text(encoding="utf-8", errors="ignore")
        if fp.suffix == ".py":
            for (name, labels, kind) in extract_from_python(txt):
                if name.startswith("atr_"):
                    found.append((name, labels, kind, str(fp.relative_to(REPO_ROOT))))
        else:
            for (name, labels, kind) in extract_from_rust(txt):
                if name.startswith("atr_"):
                    found.append((name, labels, kind, str(fp.relative_to(REPO_ROOT))))

    # Deduplicate (name, labels, kind, file) not necessary; we’ll validate all occurrences.
    errors: List[str] = []

    # 1) Unknown metrics
    for (name, labels, kind, file) in found:
        if name not in allowed_metrics:
            errors.append(f"Unknown metric name: {name} (kind={kind}) in {file}")

        # 2) Forbidden labels
        for lab in labels:
            if lab in forbidden_label_keys:
                errors.append(f"Forbidden label key '{lab}' on metric {name} in {file}")

            if lab and (lab not in allowed_label_keys):
                errors.append(f"Label key '{lab}' not in allowlist on metric {name} in {file}")

        # 3) Counter naming convention (best-effort)
        if kind == "Counter":
            if not any(name.endswith(suf) for suf in counter_suffixes):
                errors.append(f"Counter metric must end with {counter_suffixes}: {name} in {file}")

    if not found:
        errors.append("No ATR metrics found in repo (expected atr_* metrics).")

    if errors:
        print("[FAIL] Metrics contract violations:")
        for e in errors:
            print(f" - {e}")
        print("\nHint: update monitoring/metrics_contract.json OR fix metric/labels in code.")
        return 1

    print(f"[OK] Metrics contract satisfied. Found {len(found)} atr_* metric occurrences.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
