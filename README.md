# ATR Core Server (Class D)

ATR (Aetherium Transmission & Retrieval) คือ **Class D Deep Core Server** ที่ทำหน้าที่เป็น **Ground Truth Authority** สำหรับการรับ event แบบกำหนดผลได้ (deterministic admission), การบันทึกความจริงแบบแก้ไขย้อนหลังไม่ได้ (immutable truth), และการเผยแพร่สตรีมตามรูปแบบ canonical อย่างเคร่งครัด.

> ATR Core **ไม่ใช่** application runtime และต้องคงความเป็น business-logic agnostic ตลอดเวลา

---

## 1) System Structure (โครงสร้างระบบตามแกนหลัก)

ATR ใช้โมเดล **3-Axis Architecture**:

1. **Transport Axis**  
   รับ/ส่งข้อมูลผ่าน AetherBusExtreme / JetStream โดย sidecar ต้องคืน broker sequence acknowledgement เพื่อคงลำดับและความน่าเชื่อถือของการส่ง
2. **Immune Axis**  
   บังคับตรวจสอบทุก event ตามลำดับ: **schema → canonicalization → signature → ruleset → quarantine** (ห้าม bypass)
3. **State Authority Axis (E3 Hybrid Truth)**  
   Truth จริงอยู่ที่ immutable event log; snapshot เป็นมุมมองที่ rebuild ได้เสมอ

อ่านรายละเอียดเชิงลึกเพิ่มเติมที่ [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 2) Core Invariants (ข้อกำหนดที่ห้ามละเมิด)

- Canonicalization ต้องนิยามที่ระดับ bytes และ signature ต้องลงนามบน canonical bytes เท่านั้น
- Delivery model เป็น **effectively-once** ผ่าน `event_id` + idempotent apply
- ห้ามอ้าง exactly-once หากไม่มี failure-injection proof
- External gates มีได้เพียง 4 จุด: **Ingress / Stream / Query / Admin**
- Signature verification, schema validation, quarantine flow ต้องเป็น mandatory ทั้งหมด

แหล่งอ้างอิงนโยบายหลัก: [`AGENTS.md`](AGENTS.md)

---

## 3) Repository Layout

```text
python/        ATR Core Python package (API, immune pipeline, tests)
sidecar/       ATB-ET Rust transport adapter
proto/         Transport protocol contracts
specs/         Contracts and protocol specifications
configs/       Deployment/runtime profiles
docs/          Architecture and operational documentation
reports/       Generated benchmark/performance reports
monitoring/    Metrics/dashboard assets
scripts/       Benchmark and verification entrypoints
tools/         Contract/performance helper tools
```

---

## 4) Key References

- Technical specification: [`SPEC.md`](SPEC.md)
- Contributor policy: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Newcomer onboarding checklist: [`docs/NEWCOMER_ONBOARDING_CHECKLIST.md`](docs/NEWCOMER_ONBOARDING_CHECKLIST.md)
- Benchmark contract: [`specs/benchmark_contract.yaml`](specs/benchmark_contract.yaml)
- Performance model: [`docs/AETHERBUS_TACHYON_SPEC_TH.md`](docs/AETHERBUS_TACHYON_SPEC_TH.md)
- Main performance report: [`reports/atr_performance_report.md`](reports/atr_performance_report.md)
- Formula estimator tool: [`tools/perf_estimator.py`](tools/perf_estimator.py)

---

## 5) Guidance for Safe Fixes & Improvements

### 5.1 เมื่อแก้ README / เอกสาร
- ปรับข้อความให้สอดคล้อง invariant เดิมโดยไม่เปลี่ยน semantics
- ถ้าปรับคำศัพท์เชิงสัญญา (เช่น effectively-once, E3, canonical bytes) ให้คงความหมายเดิม
- ไม่จำเป็นต้องรัน test/lint หากเปลี่ยนเฉพาะไฟล์เอกสาร

### 5.2 เมื่อแก้ core logic
- รักษา determinism: หลีกเลี่ยง logic ที่ขึ้นกับเวลา/สุ่ม/ลำดับที่ไม่คงที่
- ห้ามแตะเส้นทาง bypass ของ schema/canonical/signature/ruleset
- รักษา idempotency และ dedup ด้วย `event_id`
- ห้ามเปลี่ยนโมเดล E3 (Immutable Log + Rebuildable Snapshot)

### 5.3 เมื่อแก้ benchmark/performance
- หากมีผลต่อ acceptance criteria ต้องอัปเดตเวอร์ชันใน `benchmark_contract.yaml`
- ห้ามลดมาตรฐาน P99/P99.9 ที่ระบุในสัญญา

### 5.4 Checklist ก่อน merge
- [ ] ไม่มีการลดทอน invariant ด้าน security/validation
- [ ] ไม่มีการแอบเปลี่ยน semantics ของ truth model
- [ ] เอกสารอ้างอิงไฟล์ที่ถูกต้องและอัปเดตตรงกับโครงสร้างจริง
- [ ] หากแตะโค้ด production-critical มีหลักฐานการทดสอบที่เพียงพอ

---

## 6) Current Status

Repository นี้วางโครงเพื่อ production-grade governance ภายใต้ข้อจำกัดของ Class D อย่างเคร่งครัด.
การปรับปรุงต้องทำแบบ incremental และพิสูจน์ได้ว่า **ไม่ละเมิด determinism, immutability, strict validation และ E3 truth model**.
