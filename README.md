# Hestia - HR Management Web Application

A comprehensive HR Management System built with Next.js, FastAPI, Firebase Authentication, and Google Cloud Firestore.

## 🏗️ Tech Stack

**Frontend:** Next.js 14, TypeScript, shadcn/ui, Firebase Auth  
**Backend:** FastAPI, Firebase Admin SDK, Firestore  
**Deployment:** Vercel (frontend), Cloud Run (backend)

## 🚀 Quick Start

### Frontend
```bash
cd frontend
npm install
cp .env.local.example .env.local  # Add Firebase config
npm run dev  # http://localhost:3000
```

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Add Firebase credentials path
uvicorn app.main:app --reload  # http://localhost:8000
```

## 👥 User Roles

- **Director**: Full system access
- **HR**: Employee & policy management
- **Manager**: Team management & approvals
- **Lead**: Manage direct reportees
- **Employee**: Self-service portal

## 📱 Features

✅ Authentication & RBAC  
✅ Employee Management  
✅ Attendance Tracking  
✅ Leave Management  
✅ Task Management  
✅ Performance Reviews  
✅ Announcements  
✅ Reports & Analytics

## 📚 Documentation

- API Docs: `http://localhost:8000/docs`
- See `/backend/README.md` for detailed setup
- See `/frontend/src/` for component structure

## 🔐 Firebase Setup

1. Create Firebase project
2. Enable Email/Password Authentication
3. Create Firestore database with collections:
   - `users`, `departments`, `attendance`, `leaves`
   - `tasks`, `performance_reviews`, `announcements`, `permissions`
4. Download Admin SDK credentials

## 📄 License

Proprietary - © 2026 Joyrts
