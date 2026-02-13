"""
ATR Performance Estimator — Multi-core + Adaptive Batch + Markdown Auto Report
Document: ATR-PERF-REPORT-2026

Usage:
    python tools/perf_estimator.py

Output:
    reports/atr_performance_report.md

This is a formula-based analytical estimator, not a runtime benchmark.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple
import os


# =============================
# MODEL
# =============================


@dataclass
class PerfParams:
    # Base times (microseconds)
    t_py_us: float = 5.0
    t_bridge_us: float = 50.0
    t_persist_us: float = 0.0
    t_rust_us_per_msg: float = 0.1

    # Multi-core scaling
    cores: int = 8
    parallel_fraction: float = 0.90

    # Optional ceilings (ops/sec)
    io_ceiling_ops_sec: Optional[float] = None
    nic_ceiling_ops_sec: Optional[float] = None
    app_ceiling_ops_sec: Optional[float] = None


@dataclass
class BatchOptSpec:
    latency_budget_us: float = 0.5
    target_ops_sec: Optional[float] = None
    n_min: int = 1
    n_max: int = 65536
    use_powers_of_two: bool = True
    include_round_numbers: bool = True


# =============================
# CORE MATH
# =============================


def amdahl_speedup(cores: int, parallel_fraction: float) -> float:
    if cores <= 1:
        return 1.0
    p = max(0.0, min(1.0, parallel_fraction))
    return 1.0 / ((1.0 - p) + (p / float(cores)))


def batch_time_us(params: PerfParams, batch_size: int) -> float:
    if batch_size <= 0:
        raise ValueError("batch_size must be >= 1")
    return (
        params.t_py_us
        + params.t_bridge_us
        + params.t_persist_us
        + (batch_size * params.t_rust_us_per_msg)
    )


def effective_latency_us(params: PerfParams, batch_size: int) -> float:
    return batch_time_us(params, batch_size) / float(batch_size)


def throughput_single_core_ops_sec(params: PerfParams, batch_size: int) -> float:
    t_batch = batch_time_us(params, batch_size)
    return (batch_size / t_batch) * 1_000_000.0


def apply_ceilings(params: PerfParams, ops_sec: float) -> float:
    for cap in (
        params.io_ceiling_ops_sec,
        params.nic_ceiling_ops_sec,
        params.app_ceiling_ops_sec,
    ):
        if cap is not None:
            ops_sec = min(ops_sec, float(cap))
    return ops_sec


def throughput_scaled_ops_sec(params: PerfParams, batch_size: int) -> float:
    r1 = throughput_single_core_ops_sec(params, batch_size)
    speedup = amdahl_speedup(params.cores, params.parallel_fraction)
    return apply_ceilings(params, r1 * speedup)


def rust_ceiling_single_core_ops_sec(params: PerfParams) -> float:
    return 1_000_000.0 / params.t_rust_us_per_msg


def rust_ceiling_scaled_ops_sec(params: PerfParams) -> float:
    speedup = amdahl_speedup(params.cores, params.parallel_fraction)
    return apply_ceilings(params, rust_ceiling_single_core_ops_sec(params) * speedup)


# =============================
# OPTIMIZER
# =============================


def candidate_batch_sizes(spec: BatchOptSpec) -> List[int]:
    candidates = {max(1, spec.n_min), spec.n_max}

    if spec.use_powers_of_two:
        n = 1
        while n <= spec.n_max:
            if n >= spec.n_min:
                candidates.add(n)
            n <<= 1

    if spec.include_round_numbers:
        for n in (
            2,
            4,
            8,
            16,
            32,
            64,
            128,
            256,
            512,
            1000,
            1024,
            2048,
            4096,
            8192,
            16384,
            32768,
            65536,
        ):
            if spec.n_min <= n <= spec.n_max:
                candidates.add(n)

    return sorted(candidates)


def optimize_batch_size(params: PerfParams, spec: BatchOptSpec) -> Dict[str, object]:
    candidates = candidate_batch_sizes(spec)

    best: Optional[Tuple[int, float]] = None
    feasible: List[Tuple[int, float, float]] = []

    for batch_size in candidates:
        latency = effective_latency_us(params, batch_size)
        throughput = throughput_scaled_ops_sec(params, batch_size)

        if latency > spec.latency_budget_us:
            continue
        if spec.target_ops_sec is not None and throughput < spec.target_ops_sec:
            continue

        feasible.append((batch_size, throughput, latency))
        if best is None or throughput > best[1]:
            best = (batch_size, throughput)

    if best is None:
        by_latency = min(
            (
                (n, throughput_scaled_ops_sec(params, n), effective_latency_us(params, n))
                for n in candidates
            ),
            key=lambda x: x[2],
        )
        by_throughput = max(
            (
                (n, throughput_scaled_ops_sec(params, n), effective_latency_us(params, n))
                for n in candidates
            ),
            key=lambda x: x[1],
        )
        return {
            "ok": False,
            "reason": "No batch size satisfies constraints.",
            "constraints": {
                "latency_budget_us": spec.latency_budget_us,
                "target_ops_sec": spec.target_ops_sec,
                "n_min": spec.n_min,
                "n_max": spec.n_max,
            },
            "closest_lowest_latency": {
                "N": by_latency[0],
                "throughput_ops_sec": by_latency[1],
                "latency_us": by_latency[2],
            },
            "closest_highest_throughput": {
                "N": by_throughput[0],
                "throughput_ops_sec": by_throughput[1],
                "latency_us": by_throughput[2],
            },
        }

    n_best, throughput_best = best
    latency_best = effective_latency_us(params, n_best)
    frontier = [
        {"N": n, "throughput_ops_sec": t, "latency_us": l}
        for (n, t, l) in sorted(feasible, key=lambda x: x[1], reverse=True)[:5]
    ]

    return {
        "ok": True,
        "best": {
            "N": n_best,
            "throughput_ops_sec": throughput_best,
            "latency_us": latency_best,
        },
        "constraints": {
            "latency_budget_us": spec.latency_budget_us,
            "target_ops_sec": spec.target_ops_sec,
            "n_min": spec.n_min,
            "n_max": spec.n_max,
        },
        "frontier_top5": frontier,
    }


def estimate_curve(params: PerfParams, batch_sizes: Iterable[int]) -> Dict[int, Dict[str, float]]:
    out: Dict[int, Dict[str, float]] = {}
    speedup = amdahl_speedup(params.cores, params.parallel_fraction)

    for n in batch_sizes:
        out[n] = {
            "latency_us_per_msg": effective_latency_us(params, n),
            "throughput_single_core_ops_sec": throughput_single_core_ops_sec(params, n),
            "throughput_scaled_ops_sec": throughput_scaled_ops_sec(params, n),
            "amdahl_speedup": speedup,
        }
    return out


# =============================
# REPORTING
# =============================


def _fmt_cap(x: Optional[float]) -> str:
    return "none" if x is None else f"{x:,.0f}"


def _recommendation(params: PerfParams, spec: BatchOptSpec, opt: Dict[str, object]) -> List[str]:
    recs: List[str] = []

    if params.t_persist_us <= 0.0:
        recs.append(
            "Profile detected: Transport (no persistence). Keep latency_budget_us strict (0.2–1.0 µs/msg) and target near Rust ceiling."
        )
    else:
        recs.append(
            "Profile detected: Class D persisted path. Set realistic t_persist_us and io_ceiling_ops_sec from measured storage behavior."
        )

    if opt.get("ok"):
        best = opt["best"]
        recs.append(
            f"Use batch size N={best['N']} as the default candidate (verify with real traffic and queue-depth behavior)."
        )
    else:
        recs.append(
            "No feasible batch under current constraints: relax latency_budget_us, lower target_ops_sec, or reduce control-plane overhead (t_py_us/t_bridge_us/t_persist_us)."
        )

    if params.io_ceiling_ops_sec is None and params.t_persist_us > 0:
        recs.append("Persisted mode without io_ceiling_ops_sec may overestimate throughput; set a storage ceiling.")

    if spec.target_ops_sec is None:
        recs.append("Set target_ops_sec in CI profiles to enforce explicit throughput objectives.")

    return recs


def generate_markdown_report(params: PerfParams, spec: BatchOptSpec) -> str:
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    speedup = amdahl_speedup(params.cores, params.parallel_fraction)
    rust_single = rust_ceiling_single_core_ops_sec(params)
    rust_scaled = rust_ceiling_scaled_ops_sec(params)
    curve = estimate_curve(params, (1, 16, 64, 256, 1024, 4096, 8192))
    opt = optimize_batch_size(params, spec)

    lines: List[str] = []
    lines.append("# ATR Performance Report")
    lines.append(f"_Generated: {timestamp}_")
    lines.append("")

    lines.append("## 1) Header Metadata")
    lines.append("- Document: **ATR-PERF-REPORT-2026**")
    lines.append("- Method: **Formula-based estimator (not runtime benchmark)**")
    lines.append("")

    lines.append("## 2) System Parameters")
    lines.append(f"- Cores: **{params.cores}**")
    lines.append(f"- Parallel Fraction (P): **{params.parallel_fraction:.2f}**")
    lines.append(f"- T_py: **{params.t_py_us} µs**")
    lines.append(f"- T_bridge: **{params.t_bridge_us} µs**")
    lines.append(f"- T_persist: **{params.t_persist_us} µs**")
    lines.append(f"- T_rust/msg: **{params.t_rust_us_per_msg} µs**")
    lines.append(f"- IO cap: **{_fmt_cap(params.io_ceiling_ops_sec)} ops/sec**")
    lines.append(f"- NIC cap: **{_fmt_cap(params.nic_ceiling_ops_sec)} ops/sec**")
    lines.append(f"- APP cap: **{_fmt_cap(params.app_ceiling_ops_sec)} ops/sec**")
    lines.append("")

    lines.append("## 3) Amdahl Scaling Summary")
    lines.append(f"- Speedup S(cores={params.cores}, P={params.parallel_fraction:.2f}) = **{speedup:.2f}x**")
    lines.append("")

    lines.append("## 4) Rust Ceiling Analysis")
    lines.append(f"- Single-core Rust ceiling: **{rust_single:,.0f} ops/sec**")
    lines.append(f"- Scaled Rust ceiling (after Amdahl + caps): **{rust_scaled:,.0f} ops/sec**")
    lines.append("")

    lines.append("## 5) Batch Optimization Result")
    if opt.get("ok"):
        best = opt["best"]
        lines.append(f"- Optimal Batch Size N: **{best['N']}**")
        lines.append(f"- Throughput: **{best['throughput_ops_sec']:,.0f} ops/sec**")
        lines.append(f"- Effective Latency: **{best['latency_us']:.4f} µs/msg**")
        lines.append("")
        lines.append("Top feasible frontier:")
        lines.append("| N | Throughput (ops/sec) | Latency (µs/msg) |")
        lines.append("|---:|---:|---:|")
        for row in opt["frontier_top5"]:
            lines.append(
                f"| {row['N']} | {row['throughput_ops_sec']:,.0f} | {row['latency_us']:.4f} |"
            )
    else:
        lines.append("- ⚠ No feasible batch size satisfies current constraints.")
    lines.append("")

    lines.append("## 6) Performance Curve Table")
    lines.append("| Batch | Throughput Scaled (ops/sec) | Throughput 1-core (ops/sec) | Latency (µs/msg) |")
    lines.append("|---:|---:|---:|---:|")
    for n, metrics in curve.items():
        lines.append(
            f"| {n} | {metrics['throughput_scaled_ops_sec']:,.0f} | "
            f"{metrics['throughput_single_core_ops_sec']:,.0f} | {metrics['latency_us_per_msg']:.4f} |"
        )
    lines.append("")

    lines.append("## 7) Constraint Diagnostics")
    lines.append(f"- latency_budget_us: **{spec.latency_budget_us}**")
    lines.append(f"- target_ops_sec: **{spec.target_ops_sec if spec.target_ops_sec is not None else 'none'}**")
    lines.append(f"- batch range: **[{spec.n_min}, {spec.n_max}]**")
    if not opt.get("ok"):
        low_lat = opt["closest_lowest_latency"]
        hi_thr = opt["closest_highest_throughput"]
        lines.append(
            f"- Closest (lowest latency): N={low_lat['N']}, throughput={low_lat['throughput_ops_sec']:,.0f}, latency={low_lat['latency_us']:.4f}"
        )
        lines.append(
            f"- Closest (highest throughput): N={hi_thr['N']}, throughput={hi_thr['throughput_ops_sec']:,.0f}, latency={hi_thr['latency_us']:.4f}"
        )
    lines.append("")

    lines.append("## 8) Final Recommendation")
    for rec in _recommendation(params, spec, opt):
        lines.append(f"- {rec}")

    lines.append("")
    lines.append("---")
    lines.append("This report is an analytical model and should be reconciled with production telemetry.")

    return "\n".join(lines)


def run_default() -> str:
    params = PerfParams()
    spec = BatchOptSpec()

    report = generate_markdown_report(params, spec)
    os.makedirs("reports", exist_ok=True)
    output_path = "reports/atr_performance_report.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    return output_path


if __name__ == "__main__":
    path = run_default()
    print(f"Report generated: {path}")
