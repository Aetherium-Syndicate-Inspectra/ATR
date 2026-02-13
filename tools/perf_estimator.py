"""
ATR Performance Estimator (Formula-Based) — Multi-core Scaling
Document: ATR-PERF-EST-2026-MC

This is NOT a benchmark.
It estimates theoretical throughput/latency based on a 3-tier hybrid model.

Model:
T_batch = T_py + T_ffi + T_persist + N*T_rust
R1(N)   = N / T_batch  (single-core equivalent, ops/us)
R(N)    = R1(N) * Speedup(cores, parallel_fraction)  clamped by ceilings

Where Speedup uses Amdahl's Law:
S = 1 / ((1-P) + P/cores)

All times are in microseconds unless otherwise stated.
"""

from dataclasses import dataclass
from typing import Dict, Iterable, Optional


@dataclass
class PerfParams:
    # --- Base times (microseconds) ---
    # Control plane overhead per batch (Python orchestration / routing)
    t_py_us: float = 5.0

    # Bridge overhead per batch (gRPC/FFI/marshaling/copy)
    t_bridge_us: float = 50.0

    # Persistence overhead per batch (JetStream sync ack, disk flush, etc.)
    t_persist_us: float = 0.0

    # Rust data-plane cost per message (hot path)
    t_rust_us_per_msg: float = 0.1

    # --- Scaling parameters ---
    cores: int = 1

    # Fraction of the workload that can scale with cores (0..1)
    # Typically Rust dataplane + parts of bridge can scale; Python often does not.
    parallel_fraction: float = 0.90

    # Optional clamp ceilings (ops/sec)
    # Useful to avoid unrealistic numbers when other bottlenecks exist.
    io_ceiling_ops_sec: Optional[float] = None  # e.g., disk/NVMe or JetStream ceiling
    nic_ceiling_ops_sec: Optional[float] = None  # e.g., NIC / network ceiling
    app_ceiling_ops_sec: Optional[float] = None  # any other hard cap you want to apply


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


def throughput_single_core_ops_sec(params: PerfParams, batch_size: int) -> float:
    """Single-core equivalent throughput (before multi-core scaling)."""
    t_batch = batch_time_us(params, batch_size)  # us
    return (batch_size / t_batch) * 1_000_000.0


def effective_latency_us_per_msg(params: PerfParams, batch_size: int) -> float:
    """Effective per-message service time from batched model (us/msg)."""
    return batch_time_us(params, batch_size) / float(batch_size)


def apply_ceilings(params: PerfParams, ops_sec: float) -> float:
    caps = [
        params.io_ceiling_ops_sec,
        params.nic_ceiling_ops_sec,
        params.app_ceiling_ops_sec,
    ]
    for cap in caps:
        if cap is not None:
            ops_sec = min(ops_sec, float(cap))
    return ops_sec


def throughput_scaled_ops_sec(params: PerfParams, batch_size: int) -> float:
    """Multi-core scaled throughput with Amdahl + ceilings."""
    r1 = throughput_single_core_ops_sec(params, batch_size)
    speedup = amdahl_speedup(params.cores, params.parallel_fraction)
    return apply_ceilings(params, r1 * speedup)


def rust_ceiling_single_core_ops_sec(params: PerfParams) -> float:
    """Theoretical ceiling if only Rust hot path matters (single core)."""
    return 1_000_000.0 / params.t_rust_us_per_msg


def rust_ceiling_scaled_ops_sec(params: PerfParams) -> float:
    """Scaled Rust ceiling using Amdahl (still subject to ceilings)."""
    r1 = rust_ceiling_single_core_ops_sec(params)
    speedup = amdahl_speedup(params.cores, params.parallel_fraction)
    return apply_ceilings(params, r1 * speedup)


def estimate_curve(
    params: PerfParams,
    batch_sizes: Iterable[int] = (1, 10, 100, 1000, 4096, 8192),
) -> Dict[int, Dict[str, float]]:
    results: Dict[int, Dict[str, float]] = {}
    speedup = amdahl_speedup(params.cores, params.parallel_fraction)

    for batch_size in batch_sizes:
        r1 = throughput_single_core_ops_sec(params, batch_size)
        r_scaled = throughput_scaled_ops_sec(params, batch_size)
        results[batch_size] = {
            "throughput_single_core_ops_sec": r1,
            "throughput_scaled_ops_sec": r_scaled,
            "effective_latency_us_per_msg": effective_latency_us_per_msg(params, batch_size),
            "amdahl_speedup": speedup,
        }
    return results


def _fmt_cap(x: Optional[float]) -> str:
    return "none" if x is None else f"{x:,.0f}"


if __name__ == "__main__":
    # Defaults are illustrative. Tune them to your measured numbers later.
    params = PerfParams(
        t_py_us=5.0,
        t_bridge_us=50.0,
        t_persist_us=0.0,
        t_rust_us_per_msg=0.1,
        cores=8,
        parallel_fraction=0.90,
        # Example ceilings (uncomment if needed):
        # io_ceiling_ops_sec=2_000_000,   # e.g. persisted path cap
        # nic_ceiling_ops_sec=10_000_000, # e.g. network cap
    )

    curve = estimate_curve(params)

    print("=== ATR Performance Estimator (Multi-core) ===")
    print(f"Cores: {params.cores}")
    print(f"Parallel fraction P: {params.parallel_fraction:.2f}")
    print(f"Amdahl speedup S: {amdahl_speedup(params.cores, params.parallel_fraction):.2f}x")
    print()
    print("Times (µs):")
    print(f"  T_py      = {params.t_py_us}")
    print(f"  T_bridge  = {params.t_bridge_us}")
    print(f"  T_persist = {params.t_persist_us}")
    print(f"  T_rust/msg= {params.t_rust_us_per_msg}")
    print()
    print("Ceilings (ops/sec):")
    print(f"  IO  cap   = {_fmt_cap(params.io_ceiling_ops_sec)}")
    print(f"  NIC cap   = {_fmt_cap(params.nic_ceiling_ops_sec)}")
    print(f"  APP cap   = {_fmt_cap(params.app_ceiling_ops_sec)}")
    print()

    print(f"Rust ceiling (single-core) ≈ {rust_ceiling_single_core_ops_sec(params):,.0f} ops/sec")
    print(f"Rust ceiling (scaled)      ≈ {rust_ceiling_scaled_ops_sec(params):,.0f} ops/sec")
    print()

    for batch_size, metrics in curve.items():
        print(
            f"Batch {batch_size:5d} | "
            f"R1 ≈ {metrics['throughput_single_core_ops_sec']:>12,.0f} ops/s | "
            f"R ≈ {metrics['throughput_scaled_ops_sec']:>12,.0f} ops/s | "
            f"Latency ≈ {metrics['effective_latency_us_per_msg']:>8.4f} µs/msg"
        )
