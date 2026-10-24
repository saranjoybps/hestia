import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()  # load backend/.env

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

sql_path = os.path.join(os.path.dirname(__file__), '..', 'supabase', 'init_schema.sql')
with open(sql_path, 'r', encoding='utf-8') as f:
    sql = f.read()

# split statements naively on ';' (good enough for init schema)
for stmt in sql.split(';'):
    stmt = stmt.strip()
    if stmt:
        cur.execute(stmt)

cur.close()
conn.close()
print('Schema migration completed.')