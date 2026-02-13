#!/usr/bin/env python3
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]

IGNORE_DIRS = {
    ".git", ".github", ".venv", "venv", "__pycache__", "node_modules", "dist", "build",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "target"
}

# Python: prometheus_client Counter/Gauge/Histogram/Summary("name", "help", labelnames=[...])
PY_METRIC_DEF = re.compile(
    r"""\b(?P<kind>Counter|Gauge|Histogram|Summary)\s*\(\s*["'](?P<name>[^"']+)["']""",
    re.MULTILINE,
)
PY_LABELNAMES_KW = re.compile(r"""labelnames\s*=\s*(?P<lst>\[[^\]]*\]|\([^\)]*\))""", re.MULTILINE)
PY_LABELS_POS = re.compile(
    r"""\b(?:Counter|Gauge|Histogram|Summary)\s*\(\s*["'][^"']+["']\s*,\s*["'][^"']*["']\s*,\s*(?P<lst>\[[^\]]*\]|\([^\)]*\))""",
    re.MULTILINE,
)

# Rust: best-effort string literal scan + labels in &["a","b"] near it
RUST_METRIC_NAME = re.compile(r"""["'](?P<name>atr_[a-z0-9_]+)["']""", re.MULTILINE)
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

def parse_labels(lst: str) -> List[str]:
    return STR_IN_LIST.findall(lst)

def extract_from_python(text: str) -> List[Tuple[str, List[str], str]]:
    results: List[Tuple[str, List[str], str]] = []
    for m in PY_METRIC_DEF.finditer(text):
        kind = m.group("kind")
        name = m.group("name")

        # capture small window of constructor args
        tail = text[m.start(): m.start() + 800]

        labels: List[str] = []
        m_kw = PY_LABELNAMES_KW.search(tail)
        if m_kw:
            labels = parse_labels(m_kw.group("lst"))
        else:
            m_pos = PY_LABELS_POS.search(tail)
            if m_pos:
                labels = parse_labels(m_pos.group("lst"))

        results.append((name, labels, kind))
    return results

def extract_from_rust(text: str) -> List[Tuple[str, List[str], str]]:
    results: List[Tuple[str, List[str], str]] = []
    for m in RUST_METRIC_NAME.finditer(text):
        name = m.group("name")
        window = text[max(0, m.start() - 400): m.start() + 800]
        labels: List[str] = []
        m_labels = RUST_LABELS.search(window)
        if m_labels:
            labels = parse_labels("[" + m_labels.group("lst") + "]")
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

    found: List[Tuple[str, List[str], str, str]] = []  # (name, labels, kind, file)

    for fp in iter_source_files(REPO_ROOT):
        txt = fp.read_text(encoding="utf-8", errors="ignore")
        rel = str(fp.relative_to(REPO_ROOT))

        if fp.suffix == ".py":
            for (name, labels, kind) in extract_from_python(txt):
                if name.startswith("atr_"):
                    found.append((name, labels, kind, rel))
        else:
            for (name, labels, kind) in extract_from_rust(txt):
                if name.startswith("atr_"):
                    found.append((name, labels, kind, rel))

    errors: List[str] = []

    if not found:
        errors.append("No ATR metrics found in repo (expected atr_* metrics).")

    for (name, labels, kind, file) in found:
        # Metric name allowlist
        if name not in allowed_metrics:
            errors.append(f"Unknown metric name: {name} (kind={kind}) in {file}")

        # Label allow/deny rules
        for lab in labels:
            if lab in forbidden_label_keys:
                errors.append(f"Forbidden label key '{lab}' on metric {name} in {file}")
            if lab and (lab not in allowed_label_keys):
                errors.append(f"Label key '{lab}' not in allowlist on metric {name} in {file}")

        # Counter naming rule (only for Python counters we can detect)
        if kind == "Counter":
            if not any(name.endswith(suf) for suf in counter_suffixes):
                errors.append(f"Counter metric must end with {counter_suffixes}: {name} in {file}")

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
