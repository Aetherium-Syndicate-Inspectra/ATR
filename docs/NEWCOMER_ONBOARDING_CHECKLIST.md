# Newcomer Onboarding Checklist (ATR Core Server - Class D)

เอกสารนี้ใช้สำหรับ onboard ผู้เข้าร่วมใหม่ให้ทำงานกับ ATR Core อย่างปลอดภัย โดยยึด invariants ของระบบเป็นแกนกลาง

## 0) Mindset ก่อนเริ่ม

- [ ] เข้าใจว่า ATR Core เป็น **Deep Core infrastructure** ที่เน้น deterministic behavior, immutable truth และ strict validation
- [ ] ยืนยันว่าไม่พยายามเพิ่มช่องทาง bypass ในสายตรวจสอบหลัก (schema / canonicalization / signature / ruleset / quarantine)
- [ ] เข้าใจว่า truth model เป็น **E3**: event log = immutable truth, snapshot = rebuildable view

## 1) อ่านเอกสารหลักตามลำดับ

- [ ] อ่านภาพรวมระบบใน [`README.md`](../README.md)
- [ ] อ่านโครงสร้างเชิงลึกใน [`ARCHITECTURE.md`](../ARCHITECTURE.md)
- [ ] อ่านสเปกหลักใน [`SPEC.md`](../SPEC.md)
- [ ] อ่านข้อกำหนดผู้พัฒนาใน [`CONTRIBUTING.md`](../CONTRIBUTING.md)
- [ ] อ่าน invariant contracts ใน [`specs/invariants.md`](../specs/invariants.md)
- [ ] อ่าน canonicalization contract ใน [`specs/canonicalization.md`](../specs/canonicalization.md)
- [ ] อ่าน benchmark acceptance ใน [`specs/benchmark_contract.yaml`](../specs/benchmark_contract.yaml)

## 2) ทำความเข้าใจขอบเขตรับผิดชอบของแต่ละแกน

- [ ] ระบุได้ว่า ATR Core (Python) บังคับ Immune Axis: schema → canonicalization → signature → ruleset → quarantine
- [ ] ระบุได้ว่า ATB-ET sidecar (Rust) รับผิดชอบ transport/persistence adapter และ broker sequence ack
- [ ] ระบุ external gates ที่อนุญาตมีเพียง 4 จุด: Ingress / Stream / Query / Admin

## 3) เตรียมสภาพแวดล้อมสำหรับงานเอกสารและงานโค้ด

- [ ] เปิดใช้งานเครื่องมือที่จำเป็นของภาษา Python และ Rust ตามที่ repo ใช้
- [ ] ตรวจสอบว่ามองเห็นโฟลเดอร์หลักครบ: `python/`, `sidecar/`, `proto/`, `specs/`, `configs/`, `scripts/`, `tools/`
- [ ] ตรวจสอบว่าสามารถรันคำสั่ง git พื้นฐาน (status, diff, commit) ได้

## 4) Rules of Engagement ระหว่างแก้ไขงาน

- [ ] หากแก้เฉพาะเอกสาร/คอมเมนต์/formatting: ไม่ต้องรัน test/lint workflows
- [ ] หากแก้ source หรือ schema ที่กำหนด: ต้องรัน test/lint ที่เกี่ยวข้องก่อนส่ง
- [ ] ไม่เพิ่มพฤติกรรม non-deterministic (time/random/order-dependent) ใน core logic
- [ ] รักษา idempotency + deduplication ผ่าน `event_id`
- [ ] ไม่ปรับ semantics ของ E3 truth model
- [ ] ไม่ทำให้ signature verification หรือ schema validation กลายเป็น optional

## 5) Pre-PR Checklist (ขั้นต่ำก่อนขอ review)

- [ ] Scope ของการเปลี่ยนแปลงชัดเจน และไม่เกินเจตนาของงาน
- [ ] มีคำอธิบายผลกระทบต่อ invariants อย่างชัดเจนใน PR description
- [ ] หากแตะ benchmark acceptance criteria: มีการอัปเดตเวอร์ชันใน benchmark contract แล้ว
- [ ] ไม่มีการลดมาตรฐาน P99/P99.9 ตามสัญญา
- [ ] มีหลักฐานการทดสอบตามประเภทการเปลี่ยนแปลง (ถ้ามีการแก้ source/schema)

## 6) สัญญาณเตือนที่ต้องหยุดและทบทวนทันที

- [ ] พบแนวทางที่ต้อง bypass validation pipeline เพื่อให้ “ผ่านเร็วขึ้น”
- [ ] พบการอ้าง exactly-once โดยไม่มี failure injection proof
- [ ] พบการเปลี่ยน canonical bytes definition หรือ signature domain โดยไม่ปรับสเปกอย่างเป็นทางการ
- [ ] พบการทำ snapshot เป็นแหล่ง truth หลักแทน immutable event log

---

Checklist นี้เป็น baseline สำหรับ newcomer ทุกคน และควรถูกอัปเดตเมื่อมีการเปลี่ยน contract/invariant ของระบบเท่านั้น
