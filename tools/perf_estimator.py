"""ATR formula-based performance estimator.

Document: ATR-PERF-EST-2026
Purpose: Estimate theoretical throughput/latency envelopes of the Python+Rust
hybrid architecture from timing assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable


@dataclass(frozen=True)
class PerfParams:
    """Timing parameters in microseconds."""

    t_py_us: float = 5.0
    t_ffi_us: float = 50.0
    t_rust_us: float = 0.1
    t_persist_us: float = 0.0


@dataclass(frozen=True)
class AmdahlParams:
    """Amdahl's law inputs.

    rust_fraction: Fraction moved to Rust (P)
    rust_speedup: Rust speedup factor over Python for moved workload (S)
    """

    rust_fraction: float
    rust_speedup: float


def batch_time_us(params: PerfParams, batch_size: int) -> float:
    _validate_batch_size(batch_size)
    return (
        params.t_py_us
        + params.t_ffi_us
        + params.t_persist_us
        + (batch_size * params.t_rust_us)
    )


def throughput_ops_per_sec(params: PerfParams, batch_size: int) -> float:
    t_batch_us = batch_time_us(params, batch_size)
    return (batch_size / t_batch_us) * 1_000_000


def effective_latency_us(params: PerfParams, batch_size: int) -> float:
    return batch_time_us(params, batch_size) / batch_size


def rust_ceiling_ops_per_sec(params: PerfParams) -> float:
    _validate_positive(params.t_rust_us, "t_rust_us")
    return 1_000_000 / params.t_rust_us


def amdahl_speedup(params: AmdahlParams) -> float:
    p = params.rust_fraction
    s = params.rust_speedup
    if not 0.0 <= p <= 1.0:
        raise ValueError("rust_fraction must be in [0, 1]")
    _validate_positive(s, "rust_speedup")
    return 1.0 / ((1.0 - p) + (p / s))


def estimate_curve(
    params: PerfParams,
    batch_sizes: Iterable[int] = (1, 10, 100, 1000, 4096, 8192),
) -> Dict[int, Dict[str, float]]:
    result: Dict[int, Dict[str, float]] = {}
    for batch in batch_sizes:
        result[batch] = {
            "throughput_ops_sec": throughput_ops_per_sec(params, batch),
            "latency_us_per_msg": effective_latency_us(params, batch),
        }
    return result


def _validate_batch_size(batch_size: int) -> None:
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")


def _validate_positive(value: float, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be > 0")


def _format_rate(rate: float) -> str:
    return f"{rate:,.0f}"


def main() -> None:
    perf = PerfParams()
    curve = estimate_curve(perf)

    print("=== ATR Formula-Based Performance Estimator ===")
    print(f"Rust ceiling (1 / T_rust): {_format_rate(rust_ceiling_ops_per_sec(perf))} ops/sec")
    print()

    for batch, metrics in curve.items():
        print(
            f"Batch {batch:5d} | "
            f"Throughput ~ {metrics['throughput_ops_sec']:>12,.0f} ops/sec | "
            f"Latency ~ {metrics['latency_us_per_msg']:>8.4f} us/msg"
        )

    example = AmdahlParams(rust_fraction=0.95, rust_speedup=100.0)
    print()
    print(
        "Amdahl example (P=0.95, S=100): "
        f"{amdahl_speedup(example):.2f}x max end-to-end speedup"
    )


if __name__ == "__main__":
    main()
