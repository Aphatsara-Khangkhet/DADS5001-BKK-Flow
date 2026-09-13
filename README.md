# Bangkok Traffic Mini Project

สถานะ: เตรียมข้อมูลและ Data Feasibility / Matching Audit แล้ว รอผู้ใช้ตรวจรายงานก่อน EDA และกราฟ

แหล่งข้อมูลรอบนี้คือไฟล์ `bangkok_traffic_2560_Present (NotFinal).xlsx` ชีต `traffic_data` ที่ผู้ใช้ให้มา ขอบเขตมีนาคม 2017–พฤษภาคม 2026 เป็นข้อมูลฉบับร่าง ไม่มีการดึงข้อมูลจราจรเพิ่มเติม

## กติกาที่ใช้

- ใช้ `covid_period` ในไฟล์เป็นกลุ่มหลักโดยตรง ไม่คำนวณใหม่จากวันที่
- `Date`, `month`, `year` เป็นวัน เดือน ปีของรายงาน; `survey_date` เป็นวันสำรวจจริง ความต่างระหว่างสองชุดไม่ใช่เหตุให้ตัดข้อมูล
- แทนช่องว่างและ `-` ในจำนวนรถ 6 ประเภทด้วย 0 ตามคำสั่งผู้ใช้ พร้อมเก็บค่าเดิมและ log การเปลี่ยน
- ชื่อสถานที่ปรับเฉพาะ Unicode และ whitespace ไม่ fuzzy match
- ไม่ลบแถวดิบ ตัวเลขทศนิยม/ข้อความที่ยังตีความไม่ได้และคีย์สำรวจซ้ำถูกกันจากชุด candidate ชั่วคราว และมีรายการให้ตรวจ
- ชุด candidate ไม่ใช่ข้อมูลที่รับรองเสร็จแล้ว ช่วงเวลาสำรวจต้องตรงกันก่อนเปรียบเทียบ แม้จะแปลงเป็นจำนวนรถต่อชั่วโมงก็ตาม

## เปิดงาน

- `notebooks/01_data_feasibility_matching.ipynb`: notebook สำหรับรัน audit ใหม่
- `outputs/current_audit/Data_Feasibility_Matching_Audit.md`: ผลรอบล่าสุด ใช้แทนรายงานเดิมใน outputs/draft_audit_20260913
- `outputs/current_audit/matching_summary.csv`: จำนวนตัวอย่างตามเงื่อนไข matching
- `outputs/current_audit/zero_assumption_log.csv`: เซลล์ที่แทนด้วย 0
- `data/interim/traffic_audited.csv`: ทุกแถวเดิมพร้อมคอลัมน์ audit
- `data/processed/traffic_candidates.csv`: แถว candidate ก่อนเลือกแบบ matching
- `docs/data_dictionary.md` และ `docs/analysis_plan.md`: ความหมายคอลัมน์และขั้นต่อไป

## รันกับข้อมูลฉบับใหม่

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/traffic_audit.py --input "พาธไฟล์ฉบับใหม่.xlsx"
.\.venv\Scripts\python.exe src/write_audit_report.py
```

Notebook ใช้ snapshot ภายในโปรเจกต์เป็นค่าเริ่มต้น ถ้าต้องการใช้ไฟล์ใหม่ตั้ง environment variable `TRAFFIC_INPUT` เป็นพาธ Excel ก่อนรัน Notebook ไม่เขียนทับไฟล์ต้นฉบับ เก็บ snapshot ตาม SHA-256 และผลรอบล่าสุดใน outputs/current_audit

การรันโดยทั่วไปใช้ dependency ตาม requirements.txt สภาพแวดล้อมที่ทดสอบรอบนี้ใช้ Python แบบ bundled ของ Codex ผ่าน .venv ที่สืบทอด Pandas/NumPy/openpyxl และเพิ่ม Jupyter ภายในโปรเจกต์

## การเผยแพร่และ AI

ยังไม่ได้เผยแพร่หรือ push GitHub ควรยืนยันสิทธิ์เผยแพร่ข้อมูลต้นทางก่อน ภายใน .gitignore กันข้อมูลดิบ/ผลที่มีแถวข้อมูลและ .venv ไว้

AI ช่วยเขียน pipeline, ตรวจ schema/quality/matching และจัดทำเอกสาร ผู้ใช้เป็นผู้กำหนดนิยามวันที่ กลุ่ม COVID และสมมติฐานค่า 0 สมาชิกยังต้องตรวจแถวที่ติด flag กับหลักฐานต้นทางและเลือกชุดเปรียบเทียบก่อนสรุปผล ห้ามใช้ปริมาณรถเพียงอย่างเดียวสรุปความเร็วหรือความติดขัด และไม่อ้างเหตุและผลจาก EDA
