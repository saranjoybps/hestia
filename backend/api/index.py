"""
Vercel serverless function entry point
"""
from app.main import app

# Vercel will use this 'app' object
handler = app
