# ข้อเสนอแผนงานแก้ไขจากการตรวจสอบฐานโค้ด ATR Core

เอกสารนี้สรุป “งานที่ควรทำ” อย่างละ 1 งานตามประเภทที่ร้องขอ โดยยึด invariants ของ ATR Core (determinism, immutability, strict validation, E3 truth) และยังไม่เปลี่ยนพฤติกรรมรันไทม์ในรอบนี้

## 1) งานแก้ไขข้อความพิมพ์ผิด (Typo Fix)
**งานที่เสนอ:** แก้คำสะกดในข้อความ error code จาก `CANON_DUPLICATE_KEY_AFTER_NORMALIZE` ให้เป็น `CANON_DUPLICATE_KEY_AFTER_NORMALIZATION` และทำ mapping ย้อนกลับเพื่อ backward compatibility ระยะเปลี่ยนผ่าน

**หลักฐานที่พบ:** ข้อความ error ใช้คำกริยา `NORMALIZE` ในชื่อ code ซึ่งไม่สอดคล้องรูปแบบการตั้งชื่อสถานะเชิงนามในระบบเดียวกัน.

**ไฟล์ที่เกี่ยวข้อง:**
- `python/atr_core/core/canonicalization.py` (จุดกำเนิด error code)
- `python/atr_core/tests/test_immune.py` (assert ข้อความ error)

**นิยามเสร็จงาน (DoD):**
- เพิ่ม alias รองรับ code เดิมเพื่อไม่ทำให้ระบบที่พึ่งพา string เดิมพังทันที
- เพิ่มบันทึกการย้ายผ่านใน changelog/notes

## 2) งานแก้ไขบั๊ก (Bug Fix)
**งานที่เสนอ:** บังคับตรวจผลลัพธ์การ publish ไป quarantine ในเส้นทางปฏิเสธ event หาก broker ไม่รับ ต้องคืน 503 แทนการคืนเหตุผลเดิมทันที

**หลักฐานที่พบ:** ในเส้นทาง reject ระบบเรียก `transport.publish(...)` แต่ไม่ตรวจ `ack.accepted` ทำให้เกิด false confidence ว่า quarantine สำเร็จ ทั้งที่อาจไม่ถูกจัดเก็บจริง

**ไฟล์ที่เกี่ยวข้อง:**
- `python/atr_core/api/app.py`

**นิยามเสร็จงาน (DoD):**
- ถ้า quarantine publish ไม่สำเร็จ ให้ตอบ `HTTP 503` พร้อม error ที่บ่งชี้ว่า quarantine failed
- เก็บพฤติกรรมเดิมของการคัดแยก 400/403 ไว้เฉพาะกรณี quarantine publish สำเร็จ

## 3) งานแก้ไขคอมเมนต์/ความคลาดเคลื่อนของเอกสาร
**งานที่เสนอ:** ปรับ `README.md` ส่วน “Repository Layout” ให้สอดคล้องโครงสร้างจริง โดยแยก `reports/` ออกจาก `docs/` ให้ชัดเจน

**หลักฐานที่พบ:** README อธิบายโครงสร้างหลัก แต่ยังไม่ระบุโฟลเดอร์ `reports/` ที่มีรายงาน performance อยู่จริง ทำให้ผู้อ่านใหม่หาเอกสารผลการทดสอบไม่ตรงจุด

**ไฟล์ที่เกี่ยวข้อง:**
- `README.md`
- `reports/atr_performance_report.md`

**นิยามเสร็จงาน (DoD):**
- เพิ่มบรรทัดอธิบาย `reports/` ใน layout
- เพิ่มลิงก์อ้างอิงรายงานหลักในหัวข้อ Key References

## 4) งานปรับปรุงการทดสอบ (Test Improvement)
**งานที่เสนอ:** เพิ่ม integration test สำหรับเส้นทาง reject ที่จำลองกรณี quarantine publish ถูก broker ปฏิเสธ เพื่อยืนยันว่า API คืน 503 ตามข้อเสนอ bug fix

**หลักฐานที่พบ:** ชุดทดสอบปัจจุบันเน้น serialization/pipeline แต่ยังไม่มี test ครอบคลุม behavior ของ API เมื่อ quarantine transport ล้มเหลว

**ไฟล์ที่เกี่ยวข้อง:**
- ปัจจุบันมี: `python/atr_core/tests/test_api.py`
- ควรเพิ่ม: `python/atr_core/tests/test_app_submit_reject_path.py` (หรือรวมในไฟล์เดิม)

**นิยามเสร็จงาน (DoD):**
- ทดสอบกรณี signature fail แล้ว quarantine publish fail -> ได้ `503`
- ทดสอบกรณี signature fail แล้ว quarantine publish success -> ได้ `403`
- ทดสอบกรณี schema fail แล้ว quarantine publish success -> ได้ `400`
