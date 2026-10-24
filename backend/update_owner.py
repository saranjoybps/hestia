import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

host = 'db.dknzllzlrhbxlpdruyap.supabase.co'
port = 5432
database = 'postgres'
user = 'postgres'
password = os.getenv('SUPABASE_DB_PASSWORD')

new_firebase_uid = 'a4b8L3Z8d3gzerLgCTdc9pcDHZC2'
email = 'noreply@joyinfinity.com'
role = 'director'

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
    UPDATE public.users
    SET firebase_uid = %s, role = %s
    WHERE email = %s;
""", (new_firebase_uid, role, email))

print(f"Rows updated: {cur.rowcount}")

cur.close()
conn.close()