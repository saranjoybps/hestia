import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

host = 'db.dknzllzlrhbxlpdruyap.supabase.co'
port = 5432
database = 'postgres'
user = 'postgres'
password = os.getenv('SUPABASE_DB_PASSWORD')

conn = psycopg2.connect(
    host=host,
    port=port,
    dbname=database,
    user=user,
    password=password,
    sslmode='require'
)
conn.autocommit = True
cur = conn.cursor()

cur.execute("SELECT id, firebase_uid, email, role FROM public.users WHERE email = %s;", ('noreply@joyinfinity.com',))
rows = cur.fetchall()
for r in rows:
    print(r)

cur.close()
conn.close()