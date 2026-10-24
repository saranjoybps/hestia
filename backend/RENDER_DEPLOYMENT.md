# Hestia Backend Deployment Guide for Render

## Prerequisites
1. GitHub repository with the backend code
2. Firebase project with credentials
3. Render account (free tier works)

## Deployment Steps

### 1. Prepare Your Repository
Ensure these files are in your backend directory:
- `requirements.txt` - Python dependencies
- `render.yaml` - Render configuration (created)
- Updated `app/dependencies.py` - Supports environment variables
- Updated `app/config.py` - Includes Render domains in CORS

### 2. Push to GitHub
```bash
git add .
git commit -m "Add Render deployment configuration"
git push origin dev
```

### 3. Create Web Service on Render

#### Option A: Using render.yaml (Recommended)
1. Go to https://dashboard.render.com/
2. Click "New" → "Blueprint"
3. Connect your GitHub repository
4. Select the repository: `joyrts/joyhr`
5. Render will automatically detect `render.yaml`
6. Click "Apply"

#### Option B: Manual Setup
1. Go to https://dashboard.render.com/
2. Click "New" → "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Name**: `joyhr-backend`
   - **Region**: Oregon (US West)
   - **Branch**: `dev`
   - **Root Directory**: `backend`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### 4. Configure Environment Variables

In Render Dashboard → Your Service → Environment:

1. **FIREBASE_CREDENTIALS** (Required)
   - Go to Firebase Console → Project Settings → Service Accounts
   - Click "Generate New Private Key"
   - Copy the entire JSON content
   - Paste it as the value (as a single line JSON string)

2. **FIREBASE_PROJECT_ID** (Optional but recommended)
   - Your Firebase project ID
   - Example: `joyhr-98108`

3. **PYTHON_VERSION** (Optional)
   - Value: `3.11.0`
   - Forces Render to use Python 3.11

4. **FRONTEND_URL** (For CORS)
   - Your frontend URL (update when frontend is deployed)
   - Example: `https://joyhr-frontend.onrender.com`

### 5. Deploy

After adding environment variables:
1. Click "Manual Deploy" → "Deploy latest commit"
2. Wait for build to complete (3-5 minutes)
3. Your backend will be available at: `https://joyhr-backend.onrender.com`

## Testing Your Deployment

Test the API health:
```bash
curl https://joyhr-backend.onrender.com/
```

Test authentication endpoint:
```bash
curl https://joyhr-backend.onrender.com/api/users/me \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN"
```

## Important Notes

### Free Tier Limitations
- Services spin down after 15 minutes of inactivity
- First request after spin-down takes 30-60 seconds
- 750 hours/month of runtime (shared across all services)

### Environment Variables Format
For FIREBASE_CREDENTIALS, ensure it's a valid JSON string:
```json
{"type":"service_account","project_id":"your-project-id","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n","client_email":"..."}
```

### CORS Configuration
The backend is configured to accept requests from:
- `http://localhost:3000` (local development)
- `https://*.onrender.com` (Render deployments)

Update `app/config.py` to add your production frontend domain.

## Monitoring

- **Logs**: Render Dashboard → Your Service → Logs
- **Metrics**: Render Dashboard → Your Service → Metrics
- **Events**: Render Dashboard → Your Service → Events

## Troubleshooting

### Build Fails
- Check `requirements.txt` is valid
- Verify Python version compatibility
- Check build logs for specific errors

### Service Won't Start
- Verify `FIREBASE_CREDENTIALS` environment variable
- Check start command is correct
- Review application logs

### CORS Errors
- Add your frontend domain to `allowed_origins` in `config.py`
- Redeploy the service

## Updating Your Deployment

Render auto-deploys when you push to the configured branch:
```bash
git add .
git commit -m "Update backend"
git push origin dev
```

Or manually deploy from Render Dashboard → Manual Deploy

## Custom Domain (Optional)

To use a custom domain:
1. Render Dashboard → Your Service → Settings → Custom Domain
2. Add your domain
3. Update DNS records as instructed
4. Update CORS configuration in `config.py`

## Next Steps

1. Deploy frontend to Render/Vercel
2. Update `FRONTEND_URL` environment variable
3. Update frontend API endpoint to use your Render backend URL
4. Test end-to-end authentication and API calls
