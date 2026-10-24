import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

host = 'db.dknzllzlrhbxlpdruyap.supabase.co'
port = 5432
database = 'postgres'
user = 'postgres'
password = os.getenv('SUPABASE_DB_PASSWORD')

departments = [
    'Engineering',
    'Human Resources',
    'Finance',
    'Marketing',
    'Sales',
    'Operations',
    'Customer Support',
    'Product',
    'Design',
    'IT Administration'
]

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

for dept in departments:
    cur.execute("""
        INSERT INTO public.departments (name)
        VALUES (%s)
        ON CONFLICT (name) DO NOTHING;
    """, (dept,))
    print(f"Inserted/checked: {dept}")

cur.close()
conn.close()
print('Departments seeding completed.')