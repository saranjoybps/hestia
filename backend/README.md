# JoyHR - HR Management System Backend

FastAPI backend for JoyHR application with Firebase Authentication and Firestore database.

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure Firebase:
   - Download Firebase Admin SDK service account key
   - Save as `firebase-credentials.json` in the backend folder
   - Add to `.env` file

4. Create `.env` file:
```env
FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json
API_HOST=0.0.0.0
API_PORT=8000
FRONTEND_URL=http://localhost:3000
```

5. Run the development server:
```bash
uvicorn app.main:app --reload
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Configuration settings
│   ├── dependencies.py      # Shared dependencies (auth, etc.)
│   ├── models/              # Pydantic models
│   ├── routes/              # API route handlers
│   ├── services/            # Business logic
│   └── middleware/          # Custom middleware
├── firebase-credentials.json # Firebase Admin SDK key (gitignored)
├── .env                      # Environment variables (gitignored)
└── requirements.txt          # Python dependencies
```
