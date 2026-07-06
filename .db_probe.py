import sqlite3
con = sqlite3.connect(r'c:/Users/akash.kumar/OneDrive - psiog.com/Desktop/sem1/complisoc.db')
cur = con.cursor()
print('current_revision', cur.execute("SELECT version_num FROM alembic_version").fetchone()[0])
print('total_controls', cur.execute("SELECT COUNT(*) FROM control_catalog").fetchone()[0])
print('iso_count', cur.execute("SELECT COUNT(*) FROM control_catalog WHERE framework_name='ISO/IEC 27001:2022 Annex A'").fetchone()[0])
print('soc2_count', cur.execute("SELECT COUNT(*) FROM control_catalog WHERE framework_name='SOC 2 Trust Services Criteria (TSC) 2022'").fetchone()[0])
print('iso_sample', cur.execute("SELECT control_id, title FROM control_catalog WHERE framework_name='ISO/IEC 27001:2022 Annex A' ORDER BY control_id LIMIT 3").fetchall())
print('soc2_sample', cur.execute("SELECT control_id, title FROM control_catalog WHERE framework_name='SOC 2 Trust Services Criteria (TSC) 2022' ORDER BY control_id LIMIT 5").fetchall())
