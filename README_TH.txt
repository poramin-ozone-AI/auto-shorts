AUTO SHORTS AI — ชุดปรับปรุง Offline V3
เวอร์ชันปรับปรุง: 25 พฤศจิกายน 2026

หมายเหตุ V3:
- แก้ Workflow step "สร้างคลิป" ให้ส่ง CLOUDFLARE_ACCOUNT_ID และ CLOUDFLARE_API_TOKEN เข้า generate.py โดยตรง
- เพิ่ม Regression Test สำหรับตรวจ Workflow Environment
- V3 ผ่าน Offline/Mock tests 43/43 และ Python Compile
- ยังไม่มีการเรียก API จริง, รัน GitHub Actions, Commit หรือ Push

เป้าหมาย
- รักษาแนวความรู้แปลก ๆ, โครงเรื่อง, ภาษาไทย, Stickman หัวกลมสีขาว ผม Mohawk สีขาว/เขียว, เส้นดำหนา และภาพแนวตั้ง 9:16
- ผลิตคลิปให้ครบทุกฉาก ตรวจสอบได้ และหยุดอย่างปลอดภัยเมื่อบริการไม่พร้อม
- ใช้บริการฟรีเท่านั้น และไม่อัปเกรด/เปิด Billing เพื่อให้เกิดค่าใช้จ่ายโดยไม่ได้รับอนุญาต

ไฟล์
- generate.py: pipeline หลัก
- test_pipeline.py: Unit/Mock tests
- make-short.yml: GitHub Actions workflow (ต้องวางใน .github/workflows/)
- requirements.txt: dependencies
- ORIGINAL_generate.py: สำเนาต้นฉบับเพื่อเปรียบเทียบ ห้ามใช้แทน generate.py โดยไม่ตรวจ diff

การตั้งค่าก่อนทดสอบ API จริง (ยังไม่ได้ทดสอบในชุดนี้)
1. ใช้ Cloudflare Workers Free plan เท่านั้น และอย่าเพิ่มวิธีชำระเงิน/อัปเกรด Paid plan
2. สร้าง API Token ที่มี Workers AI Read/Write ตามเอกสาร Cloudflare
3. ตั้ง GitHub Actions Secrets: CLOUDFLARE_ACCOUNT_ID และ CLOUDFLARE_API_TOKEN
4. ตั้ง GEMINI_API_KEY ตามเดิม
5. หากไม่มี Cloudflare credentials ระบบจะหยุดก่อนเรียก Gemini เพื่อไม่เสียโควตาโดยเปล่าประโยชน์

ระบบสร้างภาพ
- Provider ที่เตรียมไว้: Cloudflare Workers AI รุ่น @cf/black-forest-labs/flux-2-klein-4b
- ใช้ multipart/form-data ตามเอกสาร REST API, ขนาด 576x1024, Seed ต่อฉาก
- รองรับผลลัพธ์ REST แบบ JSON result.image (Base64) และ raw image bytes; ถอดรหัสและตรวจ signature ก่อนบันทึก
- ไม่เรียก Pollinations แบบ anonymous/ไม่มี Key อีกต่อไป เพราะเคยเกิด HTTP 402 ซ้ำ
- HTTP 402/403/429 จะหยุดทันทีโดยไม่ Retry; HTTP 5xx และ network error ลองซ้ำได้สูงสุดอีกหนึ่งครั้ง
- จำกัดจำนวนฉากสูงสุด 18 ฉากต่อรอบ
- Cloudflare Workers AI Free allocation ปัจจุบันระบุ 10,000 Neurons/วัน; บน Workers Free การใช้เกินโควตาจะถูกปฏิเสธ แต่ต้องตรวจให้แน่ใจว่าบัญชียังคงเป็น Free plan และไม่มี Billing ที่อาจทำให้เกิดค่าใช้จ่าย
- การมีโควตาฟรีไม่ได้ยืนยันว่าภาพจะมีคุณภาพหรือคงตัวละครเหมือนกัน ต้องตรวจภาพจริง

ความปลอดภัยของภาพและ Resume
- ไม่มี preflight ที่สร้างภาพจริง
- ทุกภาพต้องมีไฟล์ภาพจริงและ marker JSON ที่เก็บ SHA-256 กับ scene fingerprint
- Resume ใช้ checkpoint version 2 เท่านั้น; checkpoint เก่า version 1 จะถูกปฏิเสธเพื่อป้องกันการนำภาพเก่ามาใช้ผิดฉาก
- ตรวจ hash, marker และข้อมูลภาพด้วย FFprobe ก่อนประกอบคลิป
- หากฉากใดสร้างภาพไม่สำเร็จ ระบบหยุดทันที ไม่ใช้ภาพฉากก่อนหน้า/พื้นสีแทน และไม่เรียก TTS ต่อ
- Resume ได้ภายใน 12 ชั่วโมงตาม workflow cache; ต้องตรวจว่า cache ของ GitHub Actions ถูกกู้คืนจริง

Wikipedia
- ตรวจประเภทบทความและความเกี่ยวข้องก่อนส่งให้ Gemini
- สำหรับ redirect/ชื่อบทความทางเลือก ต้องพบทุกคำสำคัญของหัวข้อในย่อหน้าแรก มิฉะนั้นปฏิเสธ
- การตรวจแบบนี้เป็น heuristic ไม่ใช่การยืนยันความจริงเชิงวิชาการ จึงยังต้องเปิดแหล่งข้อมูลตรวจเอง

TTS / Video QC
- Gemini TTS ยังคงเป็นลำดับหลักและ Edge TTS เป็น fallback
- TTS และการประกอบ MP4 ยังไม่ได้ทดสอบกับบริการจริง
- Final QC ตรวจ codec, resolution, FPS, audio stream และระยะเวลา
- Image QC ตรวจไฟล์/ความละเอียด/อัตราส่วน ไม่ได้ใช้ AI vision ยืนยันความหมายของภาพ

การทดสอบออฟไลน์
  python -m py_compile generate.py test_pipeline.py
  python -m unittest -v test_pipeline.py

การทดสอบชุดนี้ใช้ Mock เท่านั้น ไม่เรียก Gemini, Cloudflare, Pollinations, Wikipedia หรือ GitHub Actions

ข้อจำกัด/ความเสี่ยงที่ยังเหลือ
- ยังไม่ได้ยืนยันว่า Cloudflare account ของผู้ใช้เป็น Workers Free plan
- ยังไม่ได้เรียก Cloudflare จริง จึงยังไม่ยืนยัน response จริง, ภาพจริง, คุณภาพตัวละคร หรือโควตาที่ account ใช้ได้; การถอดรหัส Base64 ผ่าน Mock เท่านั้น
- ระบบยังไม่มี image-to-image reference character asset; ความสม่ำเสมอของตัวละครยังพึ่ง prompt และ seed เป็นหลัก
- Image QC แบบอัตโนมัติยืนยันไฟล์และสัดส่วน ไม่สามารถตัดสินว่าภาพตรงกับ narration ได้
- Gemini 503, Gemini TTS voice compatibility, Edge TTS และ Wikipedia API ยังต้องทดสอบจริงเมื่อได้รับอนุญาต

สิทธิ์การดำเนินงาน
- อนุญาตเฉพาะการแก้ไขไฟล์ในพื้นที่ทำงานและทดสอบ Offline/Mock ตามที่ผู้ใช้อนุมัติ
- ห้าม Commit, Push, รัน GitHub Actions หรือเรียก API จริงจนกว่าจะได้รับอนุญาตใหม่
