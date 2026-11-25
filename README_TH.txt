AUTO SHORTS AI — FINAL CANDIDATE
================================

วัตถุประสงค์
- สร้าง YouTube Shorts ภาษาไทยแนวความรู้แปลก ๆ
- คงหมวด เนื้อหา โครงเรื่อง และตัวละคร Stickman หัวกลมสีขาวผมโมฮอว์กสีขาว-เขียว ตาม prompt เดิม
- สร้างภาพแนวตั้ง 9:16, วิดีโอ 1080x1920, 30 FPS, H.264 และเสียง AAC

ไฟล์สำคัญ
- generate.py: pipeline หลัก
- ORIGINAL_generate.py: สำเนาไฟล์ต้นฉบับจาก ZIP ที่ผู้ใช้อัปโหลด เก็บไว้เทียบย้อนหลัง ไม่ใช่ไฟล์ที่ workflow เรียกใช้
- .github/workflows/make-short.yml: GitHub Actions แบบกดรันเอง
- test_pipeline.py: ชุดทดสอบ Offline
- requirements.txt: dependencies ที่ pin เวอร์ชันแล้ว

เงื่อนไขความปลอดภัย/โควตา
- Gemini HTTP 429: หยุดทันที ไม่ลองโมเดลสำรองต่อ
- Gemini TTS HTTP 429: หยุดทันที ไม่ลอง TTS สำรองหรือ Edge TTS ต่อ
- Pollinations HTTP 402/403/429: หยุดทันที ไม่ retry คำขอเดิม
- หากภาพฉากใดสร้างไม่ได้หรือไฟล์ภาพ decode ไม่ผ่าน จะหยุดก่อนสร้างเสียง/ประกอบวิดีโอ
- ไม่ใช้ภาพฉากก่อนหน้าแทนฉากที่ล้ม และไม่ใช้ภาพสีพื้นแทน
- การ retry ที่ยังมีอยู่จำกัดไว้สำหรับ 5xx/เครือข่ายตามโค้ด ไม่ retry 429/402/403
- ไม่มีการเปิด Billing หรือเปลี่ยนแผนบริการโดยโค้ด

Resume และ checkpoint
- checkpoint.json ถูกเขียนแบบ atomic และมีอายุใช้งานสูงสุด 12 ชั่วโมง
- เมื่อเลือก Resume ระบบจะหยุดหาก checkpoint ใช้ไม่ได้ แทนการสร้างบทใหม่โดยไม่ตั้งใจ
- ภาพที่นำกลับมาใช้ต้องมี marker, metadata, SHA-256 ตรงกับไฟล์ และ Scene Fingerprint ต้องตรงกับ prompt/style/character/seed
- ภาพเก่าที่มีเพียง .ok marker แต่ไม่มี metadata จะไม่ถูก reuse และต้องสร้างใหม่
- ก่อน reuse ภาพจะตรวจ ffprobe และให้ FFmpeg decode ภาพหนึ่งเฟรม
- GitHub Actions cache แยกตาม branch และบันทึก metadata ของภาพด้วย

วิธีติดตั้ง/ตั้งค่าใน GitHub
1. อัปโหลดไฟล์ทั้งหมดใน ZIP ไปยัง root ของ repository โดยคงโฟลเดอร์ .github/workflows ไว้
2. ใน Settings > Secrets and variables > Actions เพิ่ม Secret ชื่อ GEMINI_API_KEY
3. ตัวแปร NICHE, VOICE_NAME และ CROP_BOTTOM เป็น optional; หากไม่ตั้ง NICHE ระบบสุ่มจากหมวดที่กำหนด
4. ตรวจว่ามี Actions เปิดใช้งานใน repository และตรวจข้อกำหนด/โควตาของผู้ให้บริการด้วยตนเอง
5. ไปที่ Actions > make-short > Run workflow
6. ครั้งแรกให้ปล่อย resume = false และ publish_draft = false
7. เมื่อสำเร็จ ให้ดาวน์โหลด Artifact ชื่อ auto-shorts-output-... ซึ่งมี output.mp4, title.txt และ notes.md
8. ตรวจภาพทุกฉาก ฟังเสียง และตรวจแหล่งข้อมูลก่อนอัปโหลด YouTube

การ Resume
- ใช้ resume เฉพาะเมื่อรอบก่อนหน้าล้มหลังจาก checkpoint ถูกสร้าง และต้องการใช้บทเดิม
- cache ของ checkpoint มีอายุ/การเก็บรักษาตามนโยบาย GitHub Actions; ถ้าหา checkpoint ไม่พบ ระบบจะหยุดอย่างปลอดภัย
- ถ้าต้องการเริ่มคลิปใหม่ ให้ resume = false

การสร้าง Draft Release
- publish_draft ปิดเป็นค่าเริ่มต้น
- หากเลือก true จะสร้าง GitHub Draft Release หลัง job สร้างคลิปผ่าน QC และอัปโหลด Artifact สำเร็จ
- สิทธิ์ contents: write อยู่เฉพาะ job publish-draft ที่มีเงื่อนไข opt-in; job สร้างคลิปใช้ contents: read
- ค่าเริ่มต้นไม่มีการสร้าง Release และไม่มี schedule อัตโนมัติ

ทดสอบแบบ Offline (ไม่เรียก Gemini/Pollinations/Wikipedia)
  python -m py_compile generate.py test_pipeline.py
  python -m unittest -v test_pipeline.py

ข้อจำกัดที่ต้องเข้าใจ
- การทดสอบ Offline ไม่ยืนยันว่า Gemini, Pollinations, Wikipedia หรือ Edge TTS จะพร้อมใช้งานหรือมีโควตาในวันที่รัน
- การเรียก Gemini ผ่าน API key อาจอยู่ภายใต้ rate limit/เงื่อนไขบัญชีของผู้ใช้; โค้ดหยุดเมื่อได้รับ 429 แต่ไม่สามารถตรวจโควตาคงเหลือก่อนเรียกได้
- Pollinations เป็นบริการภายนอกที่ความพร้อมใช้งาน/นโยบายอาจเปลี่ยนได้ และไม่มีการรับประกันว่าใช้ฟรีหรือให้บริการได้ตลอดเวลา
- Preflight ภาพเป็นคำขอไปยัง Pollinations หนึ่งครั้งก่อนเริ่มขั้น Gemini และอาจนับเป็นคำขอ/ใช้ทรัพยากรของบริการ แม้เป็นเพียงการตรวจบริการ; ไม่รับประกันว่าแต่ละภาพถัดไปจะสำเร็จ
- Edge TTS เป็น fallback เฉพาะเมื่อ Gemini TTS ล้มเหลวแบบไม่ใช่ quota error; ความพร้อมใช้งานขึ้นกับบริการภายนอก
- QC ตรวจรูปแบบไฟล์/codec/ความละเอียด/ระยะเวลา ไม่สามารถรับรองความถูกต้องของข้อเท็จจริง ความเหมาะสมของภาพ หรือคุณภาพเสียงเชิงเนื้อหาได้
- ยังไม่ได้ทดสอบ end-to-end กับ API จริง และไม่ได้ทดสอบบน GitHub Actions จริงในรอบจัดทำ ZIP นี้

ความปลอดภัยของงานนี้
- ระหว่างจัดทำรุ่นนี้ไม่มีการเรียก API ภายนอก ไม่มีการรัน GitHub Actions ไม่มีการ Commit หรือ Push
- ไม่เปิด Billing และไม่เปลี่ยนแผน Cloudflare
