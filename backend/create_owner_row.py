import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

host = 'db.dknzllzlrhbxlpdruyap.supabase.co'
port = 5432
database = 'postgres'
user = 'postgres'
password = os.getenv('SUPABASE_DB_PASSWORD')

firebase_uid = 'a4b8L3Z8d3gzerLgCTdc9pcDHZC2'
email = 'noreply@joyinfinity.com'
name = 'Owner'
role = 'director'  # matches permissions table role for full access

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

cur.execute("""
    INSERT INTO public.users (firebase_uid, email, name, role)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (firebase_uid) DO UPDATE SET role = EXCLUDED.role;
""", (firebase_uid, email, name, role))

print(f"Rows affected: {cur.rowcount}")

cur.close()
conn.close()