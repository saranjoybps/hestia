import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()  # load backend/.env

host = 'db.dknzllzlrhbxlpdruyap.supabase.co'
port = 5432
database = 'postgres'
user = 'postgres'
password = os.getenv('SUPABASE_DB_PASSWORD')

firebase_uid = 'a4b8L3Z8d3gzerLgCTdc9pcDHZC2'

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

# Assuming the role column is named "role". Adjust if different.
cur.execute("UPDATE public.users SET role = 'admin' WHERE firebase_uid = %s;", (firebase_uid,))
print(f"Rows updated: {cur.rowcount}")

cur.close()
conn.close()