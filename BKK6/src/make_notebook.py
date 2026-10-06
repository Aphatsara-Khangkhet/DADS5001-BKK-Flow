"""Build a portable notebook including code, Thai font and reviewed cache."""
from pathlib import Path
import base64, io, json, zipfile

ROOT=Path(__file__).resolve().parents[1]

def make():
 payload=io.BytesIO()
 with zipfile.ZipFile(payload,'w',zipfile.ZIP_DEFLATED) as z:
  for folder in ['src','assets']:
   for p in (ROOT/folder).rglob('*'):
    if p.is_file() and '__pycache__' not in p.parts:z.write(p,p.relative_to(ROOT).as_posix())
  z.write(ROOT/'data.json','cache/presentation_data.json')
  z.write(ROOT/'docs/audit.md','cache/AUDIT.md')
  z.write(ROOT/'docs/source_check.md','docs/source_check.md')
  z.write(ROOT/'requirements.txt','requirements.txt')
  for p in (ROOT/'tables').glob('*.csv'):z.write(p,'cache/tables/'+p.name)
 encoded=base64.b64encode(payload.getvalue()).decode()
 cells=[]
 def md(text):cells.append({'cell_type':'markdown','metadata':{},'source':text.splitlines(True)})
 def code(text):cells.append({'cell_type':'code','metadata':{},'source':text.splitlines(True),'execution_count':None,'outputs':[]})
 md('# BKK Flow V6 — README และกราฟภาษาไทย\n\nสมาชิก: อภัสรา แข็งเขตต์, ธนัชชา ละครพล, พรภัสสร พัฒนไพบูลย์\n\nNotebook นี้ฝังโค้ดและฟอนต์ไว้แล้ว ไม่ต้องคัดลอก src เอง เปิดใน Colab แล้ว Run all และเลือกไฟล์ Excel ชีต traffic_data ของคุณ ผลสร้างในโฟลเดอร์ใหม่เสมอ อ่าน README ที่สร้างและทวน audit ก่อนนำเสนอ\n\nหากเป็นไฟล์เดิมที่ SHA256 ตรงกัน จะสร้างรายงานจากผลคำนวณที่ตรวจแล้ว หากเปลี่ยนข้อมูล จะตรวจและคำนวณใหม่ทั้งหมด ผลต้นทางยังไม่ใช่ข้อมูลที่รับรองทุกแถว และข้อจำกัดเรื่องสิทธิใช้ข้อมูล/นิยามล็อกดาวน์ยังคงอยู่')
 code('import os, sys, subprocess\nos.environ["OPENBLAS_NUM_THREADS"] = "1"\nif "google.colab" in sys.modules:\n    subprocess.check_call([sys.executable, "-m", "pip", "-q", "install", "pandas", "numpy", "matplotlib", "openpyxl"])\n')
 code('from pathlib import Path\nimport base64, io, zipfile, datetime, hashlib, json\nRUNTIME = Path.cwd() / ("bkk6_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f"))\nRUNTIME.mkdir()\nPAYLOAD = '+repr(encoded)+'\nwith zipfile.ZipFile(io.BytesIO(base64.b64decode(PAYLOAD))) as z:\n    for item in z.infolist():\n        assert (RUNTIME / item.filename).resolve().is_relative_to(RUNTIME.resolve())\n    z.extractall(RUNTIME)\nsys.path.insert(0, str(RUNTIME / "src"))\nimport readme_project\nprint("โค้ดพร้อมใช้งาน:", RUNTIME)\n')
 code('INPUT = None  # หากรันในเครื่อง เปลี่ยนเป็น Path(r"C:/.../new.xlsx")\nif INPUT is None:\n    try:\n        from google.colab import files\n    except ImportError:\n        raise ValueError("ระบุ INPUT เป็นพาธ Excel ของคุณในเซลล์นี้ก่อน")\n    uploaded = files.upload()\n    choices = [name for name in uploaded if name.lower().endswith(".xlsx")]\n    if len(choices) != 1:\n        raise ValueError("กรุณาเลือกไฟล์ .xlsx เพียงหนึ่งไฟล์")\n    INPUT = Path(choices[0]).resolve()\nINPUT = Path(INPUT).resolve()\nassert INPUT.is_file(), INPUT\nprint("ไฟล์:", INPUT.name)\n')
 code('sha = hashlib.sha256(INPUT.read_bytes()).hexdigest()\ncached = json.loads((RUNTIME / "cache/presentation_data.json").read_text(encoding="utf-8"))\nreuse = RUNTIME / "cache" if cached["stats"]["source_sha256"] == sha else None\nprint("ใช้ผลตรวจเดิมที่ตรง SHA256" if reuse else "ไฟล์เปลี่ยน: ตรวจข้อมูลและคำนวณใหม่")\nREPORT = readme_project.build(INPUT, reviewed_report=reuse)\nprint("README:", REPORT / "README.md")\n')
 code('from IPython.display import display, Markdown, Image, FileLink\ndisplay(FileLink(str(REPORT / "README.md")))\nfor png in sorted((REPORT / "fig").glob("*.png")):\n    display(Image(filename=str(png)))\n')
 code('import shutil\narchive = shutil.make_archive(str(REPORT.parent / ("BKK6_" + REPORT.name)), "zip", REPORT)\nprint("ชุด README และโค้ด:", archive)\ntry:\n    from google.colab import files\n    files.download(archive)\nexcept ImportError:\n    display(FileLink(archive))\n')
 notebook={'cells':cells,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python','version':'3.11'}},'nbformat':4,'nbformat_minor':5}
 for i,c in enumerate(cells):c['id']=f'bkk6-{i:02d}'
 (ROOT/'BKK6.ipynb').write_text(json.dumps(notebook,ensure_ascii=False,indent=1),encoding='utf-8')
 return ROOT/'BKK6.ipynb'

if __name__=='__main__':print(make())
