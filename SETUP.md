# JoyHR Setup Guide

This guide will help you set up the JoyHR application from scratch.

## Prerequisites

- Node.js 18+ and npm
- Python 3.9+
- Git
- Firebase account
- Google Cloud account (for deployment)

## Step 1: Firebase Project Setup

### 1.1 Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click "Add project"
3. Enter project name: `joyhr-production` (or your choice)
4. Enable Google Analytics (optional)
5. Create project

### 1.2 Enable Authentication

1. In Firebase Console, go to "Authentication"
2. Click "Get started"
3. Go to "Sign-in method" tab
4. Enable "Email/Password" provider
5. Save changes

### 1.3 Create Firestore Database

1. In Firebase Console, go to "Firestore Database"
2. Click "Create database"
3. Choose "Production mode"
4. Select location (e.g., us-central)
5. Click "Enable"

### 1.4 Setup Firestore Security Rules

Go to "Rules" tab and add:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Users collection
    match /users/{userId} {
      allow read: if request.auth != null;
      allow write: if request.auth.uid == userId || 
                     get(/databases/$(database)/documents/users/$(request.auth.uid)).data.role in ['hr', 'director'];
    }
    
    // Other collections - authenticated users can read
    match /{document=**} {
      allow read: if request.auth != null;
      allow write: if request.auth != null;
    }
  }
}
```

### 1.5 Get Firebase Configuration

1. Go to Project Settings (gear icon)
2. Scroll down to "Your apps"
3. Click "Web" icon (</>)
4. Register app name: "JoyHR Web"
5. Copy the Firebase configuration object

### 1.6 Generate Admin SDK Credentials

1. Go to Project Settings > Service accounts
2. Click "Generate new private key"
3. Save the JSON file as `firebase-credentials.json`
4. Keep this file secure (add to .gitignore)

## Step 2: Backend Setup

### 2.1 Create Virtual Environment

```bash
cd backend
python -m venv venv

# Activate virtual environment
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate
```

### 2.2 Install Dependencies

```bash
pip install -r requirements.txt
```

### 2.3 Configure Environment

Create `.env` file in backend directory:

```env
FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json
API_HOST=0.0.0.0
API_PORT=8000
FRONTEND_URL=http://localhost:3000
```

### 2.4 Add Firebase Credentials

Place the `firebase-credentials.json` file you downloaded in Step 1.6 in the backend directory.

### 2.5 Initialize Firestore Collections

Run this script to create initial data:

```bash
python scripts/init_firestore.py
```

Or manually create these collections in Firestore:
- `users`
- `departments`
- `attendance`
- `leaves`
- `tasks`
- `performance_reviews`
- `announcements`
- `permissions`
- `audit_logs`

### 2.6 Add Default Permissions

In Firestore, create documents in the `permissions` collection:

**Document ID: `director`**
```json
{
  "role": "director",
  "permissions": [
    "view_all_employees",
    "create_employee",
    "update_employee",
    "deactivate_employee",
    "approve_leaves",
    "manage_attendance",
    "generate_reports",
    "create_announcements",
    "manage_performance"
  ]
}
```

**Document ID: `hr`**
```json
{
  "role": "hr",
  "permissions": [
    "view_all_employees",
    "create_employee",
    "update_employee",
    "approve_leaves",
    "generate_reports",
    "create_announcements"
  ]
}
```

**Document ID: `manager`**
```json
{
  "role": "manager",
  "permissions": [
    "view_team_employees",
    "approve_leaves",
    "manage_attendance",
    "generate_reports",
    "manage_performance"
  ]
}
```

**Document ID: `lead`**
```json
{
  "role": "lead",
  "permissions": [
    "view_reportees",
    "mark_attendance",
    "create_performance_review"
  ]
}
```

**Document ID: `employee`**
```json
{
  "role": "employee",
  "permissions": [
    "view_own_data",
    "request_leave",
    "view_announcements"
  ]
}
```

### 2.7 Test Backend

```bash
uvicorn app.main:app --reload
```

Visit:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Step 3: Frontend Setup

### 3.1 Install Dependencies

```bash
cd frontend
npm install
```

### 3.2 Configure Environment

Create `.env.local` file in frontend directory:

```env
NEXT_PUBLIC_FIREBASE_API_KEY=your_api_key_here
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your_project.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=your_project_id
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=your_project.appspot.com
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
NEXT_PUBLIC_FIREBASE_APP_ID=your_app_id
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

Replace the values with your Firebase configuration from Step 1.5.

### 3.3 Test Frontend

```bash
npm run dev
```

Visit: http://localhost:3000

## Step 4: Create First User

Since only HR and Directors can create users, you need to manually create the first admin user:

### 4.1 Create User in Firebase Auth

1. Go to Firebase Console > Authentication
2. Click "Add user"
3. Enter email and password
4. Copy the User UID

### 4.2 Create User Document in Firestore

1. Go to Firestore Database
2. Go to `users` collection
3. Click "Add document"
4. Document ID: Use the User UID from step 4.1
5. Add fields:

```json
{
  "email": "admin@joyrts.com",
  "name": "System Administrator",
  "phone": "+1234567890",
  "role": "director",
  "department": "Management",
  "designation": "Director",
  "manager_id": null,
  "lead_id": null,
  "status": "active",
  "created_at": <current timestamp>,
  "updated_at": null
}
```

6. Save

### 4.3 Login

Now you can login to the application using the credentials from step 4.1.

## Step 5: Production Deployment

### 5.1 Deploy Backend to Cloud Run

```bash
cd backend

# Build and deploy
gcloud run deploy joyhr-api \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars FRONTEND_URL=https://your-domain.vercel.app
```

Note the service URL provided after deployment.

### 5.2 Deploy Frontend to Vercel

1. Push code to GitHub
2. Go to [Vercel Dashboard](https://vercel.com/dashboard)
3. Click "Add New Project"
4. Import your GitHub repository
5. Configure:
   - Framework Preset: Next.js
   - Root Directory: `frontend`
   - Build Command: `npm run build`
   - Output Directory: `.next`

6. Add Environment Variables:
   ```
   NEXT_PUBLIC_FIREBASE_API_KEY=...
   NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=...
   NEXT_PUBLIC_FIREBASE_PROJECT_ID=...
   NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=...
   NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=...
   NEXT_PUBLIC_FIREBASE_APP_ID=...
   NEXT_PUBLIC_API_URL=https://your-cloud-run-url/api
   ```

7. Deploy

### 5.3 Update Firebase Configuration

Update Authorized domains in Firebase Console:
1. Go to Authentication > Settings
2. Add your Vercel domain to Authorized domains

## Step 6: Post-Deployment

### 6.1 Create Departments

Use the application to create departments:
- Engineering
- Human Resources
- Finance
- Marketing
- Operations

### 6.2 Create More Users

HR or Directors can now register users through the application at `/employees/create`.

### 6.3 Setup Backup

1. Enable Firestore automatic backups in Firebase Console
2. Setup Cloud Run service monitoring
3. Configure alerting

## Troubleshooting

### Backend Issues

**Issue: Module not found**
```bash
pip install --upgrade -r requirements.txt
```

**Issue: Firebase credentials not found**
- Check the path in `.env` file
- Ensure `firebase-credentials.json` exists

### Frontend Issues

**Issue: Firebase not initialized**
- Check all environment variables are set
- Restart development server

**Issue: API calls failing**
- Ensure backend is running
- Check NEXT_PUBLIC_API_URL is correct
- Check CORS settings in backend

### Authentication Issues

**Issue: Can't login**
- Check Firebase Authentication is enabled
- Check email/password provider is enabled
- Check user exists in Firestore `users` collection

## Security Best Practices

1. Never commit `.env` files or `firebase-credentials.json`
2. Use environment variables for all secrets
3. Enable Firebase App Check for production
4. Review and tighten Firestore security rules
5. Enable Cloud Run authentication
6. Use HTTPS only in production
7. Regularly rotate Firebase service account keys
8. Enable audit logging
9. Setup monitoring and alerting
10. Regular security reviews

## Support

For issues or questions, contact the Joyrts development team.

---

**Setup completed! 🎉**

You now have a fully functional HR Management System.
