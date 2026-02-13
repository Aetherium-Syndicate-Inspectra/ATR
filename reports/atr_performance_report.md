# ATR Performance Report
_Generated: 2026-02-13T04:44:44.434347Z_

## 1) Header Metadata
- Document: **ATR-PERF-REPORT-2026**
- Method: **Formula-based estimator (not runtime benchmark)**

## 2) System Parameters
- Cores: **8**
- Parallel Fraction (P): **0.90**
- T_py: **5.0 µs**
- T_bridge: **50.0 µs**
- T_persist: **0.0 µs**
- T_rust/msg: **0.1 µs**
- IO cap: **none ops/sec**
- NIC cap: **none ops/sec**
- APP cap: **none ops/sec**

## 3) Amdahl Scaling Summary
- Speedup S(cores=8, P=0.90) = **4.71x**

## 4) Rust Ceiling Analysis
- Single-core Rust ceiling: **10,000,000 ops/sec**
- Scaled Rust ceiling (after Amdahl + caps): **47,058,824 ops/sec**

## 5) Batch Optimization Result
- Optimal Batch Size N: **65536**
- Throughput: **46,667,177 ops/sec**
- Effective Latency: **0.1008 µs/msg**

Top feasible frontier:
| N | Throughput (ops/sec) | Latency (µs/msg) |
|---:|---:|---:|
| 65536 | 46,667,177 | 0.1008 |
| 32768 | 46,281,996 | 0.1017 |
| 16384 | 45,530,398 | 0.1034 |
| 8192 | 44,098,133 | 0.1067 |
| 4096 | 41,487,934 | 0.1134 |

## 6) Performance Curve Table
| Batch | Throughput Scaled (ops/sec) | Throughput 1-core (ops/sec) | Latency (µs/msg) |
|---:|---:|---:|---:|
| 1 | 85,406 | 18,149 | 55.1000 |
| 16 | 1,330,285 | 282,686 | 3.5375 |
| 64 | 4,905,154 | 1,042,345 | 0.9594 |
| 256 | 14,946,723 | 3,176,179 | 0.3148 |
| 1024 | 30,615,143 | 6,505,718 | 0.1537 |
| 4096 | 41,487,934 | 8,816,186 | 0.1134 |
| 8192 | 44,098,133 | 9,370,853 | 0.1067 |

## 7) Constraint Diagnostics
- latency_budget_us: **0.5**
- target_ops_sec: **none**
- batch range: **[1, 65536]**

## 8) Final Recommendation
- Profile detected: Transport (no persistence). Keep latency_budget_us strict (0.2–1.0 µs/msg) and target near Rust ceiling.
- Use batch size N=65536 as the default candidate (verify with real traffic and queue-depth behavior).
- Set target_ops_sec in CI profiles to enforce explicit throughput objectives.

---
This report is an analytical model and should be reconciled with production telemetry.