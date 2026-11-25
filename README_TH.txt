ชุดปรับปรุง Auto Shorts

เป้าหมาย: คง prompt, หมวด, ตัวละคร Stickman, โครงเรื่อง, สไตล์ภาพ และรูปแบบคลิปเดิม
การปรับทางเทคนิค: ตรวจรูปแบบเสียงก่อนแปลง, ตรวจไฟล์ MP4 หลังประกอบ, ล็อก dependencies, ป้องกัน workflow ซ้อน และทดสอบโค้ดก่อนเรียก Gemini

ตำแหน่งไฟล์ใน GitHub:
- generate.py, ORIGINAL_generate.py, requirements.txt, test_pipeline.py, README_TH.txt อยู่โฟลเดอร์หลัก
- make-short.yml อยู่ที่ .github/workflows/make-short.yml เท่านั้น
- TEST_RESULTS.txt เป็นบันทึกผลตรวจ ไม่จำเป็นต้องอัปโหลด

ทดสอบแบบออฟไลน์ (ไม่เรียก Gemini):
python -m py_compile generate.py test_pipeline.py
python -m unittest -v test_pipeline.py

ข้อจำกัด:
- การทดสอบออฟไลน์ไม่ได้ยืนยันว่า Gemini, Pollinations, Wikipedia หรือ Edge TTS จะพร้อมใช้งานในวันที่รัน
- ยังไม่มี checkpoint/resume ข้าม workflow run
- ต้องดูภาพและฟังเสียงจริงก่อนเผยแพร่
- ตรวจสอบชื่อโมเดลและโควตาใน Google AI Studio ก่อนรันจริง
