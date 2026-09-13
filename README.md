# Bangkok Traffic Mini Project

สถานะ: ทำ Data Feasibility / Matching Audit และ EDA ฉบับร่าง พร้อมกราฟ 10 รูปและ Notebook ที่รันซ้ำได้แล้ว

แหล่งข้อมูลรอบนี้คือไฟล์ `bangkok_traffic_2560_Present (NotFinal) (1).xlsx` ชีต `traffic_data` ที่ผู้ใช้ให้มา ขอบเขตมีนาคม 2017–พฤษภาคม 2026 เป็นข้อมูลฉบับร่าง ไม่มีการดึงข้อมูลจราจรเพิ่มเติม

## กติกาที่ใช้

- ใช้ `covid_period` ในไฟล์เป็นกลุ่มหลักโดยตรง ไม่คำนวณใหม่จากวันที่
- `Date`, `month`, `year` เป็นวัน เดือน ปีของรายงาน; `survey_date` เป็นวันสำรวจจริง ความต่างระหว่างสองชุดไม่ใช่เหตุให้ตัดข้อมูล
- แทนช่องว่างและ `-` ในจำนวนรถ 6 ประเภทด้วย 0 ตามคำสั่งผู้ใช้ พร้อมเก็บค่าเดิมและ log การเปลี่ยน
- ชื่อสถานที่ปรับเฉพาะ Unicode และ whitespace ไม่ fuzzy match
- ไม่ลบแถวดิบ ตัวเลขทศนิยม/ข้อความที่ยังตีความไม่ได้และคีย์สำรวจซ้ำถูกกันจากชุด candidate ชั่วคราว และมีรายการให้ตรวจ
- ชุด candidate ไม่ใช่ข้อมูลที่รับรองเสร็จแล้ว ช่วงเวลาสำรวจต้องตรงกันก่อนเปรียบเทียบ แม้จะแปลงเป็นจำนวนรถต่อชั่วโมงก็ตาม

## ผล EDA เบื้องต้น

ชุดหลัก 2,612 แถว / 352 คู่ทางแยก–ถนน / 623 หน่วยสถานที่+เวลา เมื่อ Before=100 ค่ามัธยฐาน paired index เป็น During=91.6 และ After=90.4 ชุดไตรมาสรายงาน 226 แถว / 70 หน่วยได้ 87.7 และ 87.8 ตามลำดับ เป็นผลของ matched sample และ After รวมหลายปี ไม่ใช่ผลทั้งกรุงเทพฯ หรือเฉพาะปี 2026

- [Notebook EDA](notebooks/02_eda_and_visualization.ipynb)
- [รายงานผลพร้อมกราฟ](outputs/eda/EDA_Findings.md)
- [คำอธิบายกราฟทั้ง 10 พร้อมวิธีอ่านและข้อจำกัด](Read.md)
- รูป PNG อยู่ใน outputs/eda/figures จำนวน 10 รูป

## ใช้บน Google Colab

เปิด [Bangkok_Traffic_Colab.ipynb](notebooks/Bangkok_Traffic_Colab.ipynb) แล้วเลือก Runtime → Run all จากนั้นอัปโหลด Excel ที่มีชีต traffic_data ไฟล์นี้รวมโค้ด audit และ EDA ไว้ครบ ไม่ต้องอัปโหลด src และไม่ต้องรัน Notebook 01/02 ก่อน

Notebook 01/02 สำหรับใช้พร้อมโฟลเดอร์โปรเจกต์บนเครื่อง หากอัปโหลดเฉพาะไฟล์เหล่านั้นไป Colab จะพบ ModuleNotFoundError: traffic_audit เพราะเป็นโมดูลของโปรเจกต์ ไม่ใช่แพ็กเกจที่แก้ด้วย pip install traffic_audit

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
.\.venv\Scripts\python.exe src/run_project.py --input "พาธไฟล์ฉบับใหม่.xlsx" --notebooks
```

Notebook ใช้ snapshot ภายในโปรเจกต์เป็นค่าเริ่มต้น ถ้าต้องการใช้ไฟล์ใหม่ตั้ง environment variable `TRAFFIC_INPUT` เป็นพาธ Excel ก่อนรัน Notebook ไม่เขียนทับไฟล์ต้นฉบับ เก็บ snapshot ตาม SHA-256 และผลรอบล่าสุดใน outputs/current_audit

การรันโดยทั่วไปใช้ dependency ตาม requirements.txt สภาพแวดล้อมที่ทดสอบรอบนี้ใช้ Python แบบ bundled ของ Codex ผ่าน .venv ที่สืบทอด Pandas/NumPy/openpyxl และเพิ่ม Jupyter ภายในโปรเจกต์

## การเผยแพร่และ AI

ยังไม่ได้เผยแพร่หรือ push GitHub ควรยืนยันสิทธิ์เผยแพร่ข้อมูลต้นทางก่อน ภายใน .gitignore กันข้อมูลดิบ/ผลที่มีแถวข้อมูลและ .venv ไว้

AI ช่วยเขียน pipeline, ตรวจ schema/quality/matching และจัดทำเอกสาร ผู้ใช้เป็นผู้กำหนดนิยามวันที่ กลุ่ม COVID และสมมติฐานค่า 0 สมาชิกยังต้องตรวจแถวที่ติด flag กับหลักฐานต้นทางและเลือกชุดเปรียบเทียบก่อนสรุปผล ห้ามใช้ปริมาณรถเพียงอย่างเดียวสรุปความเร็วหรือความติดขัด และไม่อ้างเหตุและผลจาก EDA

ผลทั้งหมดเป็น draft สมาชิกต้องตรวจข้อจำกัดการจับคู่ ข้อมูลที่ถูก flag และสิทธิ์เผยแพร่ก่อนส่งงาน ไม่ได้สร้าง presentation/summary PDF หรือเผยแพร่ GitHub ในขั้นนี้

## ทบทวนเกณฑ์และกราฟเพิ่มเติม

[แผนตามเกณฑ์อาจารย์และสิ่งที่ศึกษาจากรุ่นพี่](docs/rubric_and_senior_review.md) แยกข้อกำหนดที่บันทึกไว้จากข้อเสนอการเล่าเรื่อง กราฟใหม่เพิ่ม coverage, distribution, paired AM/PM, location ranking, vehicle-share change และ 2026 matched-month snapshot โดยมีตารางชื่อสถานที่และขนาดตัวอย่างกำกับใน Notebook/Colab

ศึกษางานรุ่นพี่เพื่อวางโครงเรื่อง: https://github.com/techasit239/Dads-5001-Accident-Is-You-Dont-Love ไม่ใช้โค้ด/ข้อมูลอุบัติเหตุของรุ่นพี่เป็นข้อมูลโครงงานเรา
