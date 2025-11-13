# Google Drive Integration Setup Guide

## 📦 Overview
This guide walks you through setting up Google Drive integration for storing and managing Exit & Experience Letter PDFs in the Joyrts HR Management system.

## 🎯 Benefits of Google Drive Storage
- **Persistent Storage**: PDFs stored permanently in the cloud
- **Easy Sharing**: Share letter links directly with employees
- **Access Control**: Manage permissions via Google Drive
- **Version History**: Track changes to documents
- **Unlimited Storage**: No local storage constraints
- **Direct Preview**: View PDFs in browser without downloading

## 🔧 Setup Steps

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Enter project name: `joyhr-documents`
4. Click "Create"

### Step 2: Enable Google Drive API

1. In the Google Cloud Console, go to "APIs & Services" → "Library"
2. Search for "Google Drive API"
3. Click on "Google Drive API"
4. Click "Enable"

### Step 3: Create Service Account

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "Service Account"
3. Fill in the details:
   - **Service account name**: `joyhr-drive-service`
   - **Service account ID**: `joyhr-drive-service`
   - **Description**: `Service account for HR document management`
4. Click "Create and Continue"
5. **Grant access** (Optional): Skip this step
6. Click "Done"

### Step 4: Generate Service Account Key

1. In the "Credentials" page, find your service account
2. Click on the service account email
3. Go to the "Keys" tab
4. Click "Add Key" → "Create new key"
5. Select "JSON" format
6. Click "Create"
7. **Save the downloaded JSON file securely** - this is your credential file!

### Step 5: Create Google Drive Folder (Optional but Recommended)

1. Go to [Google Drive](https://drive.google.com/)
2. Create a new folder: `JoyHR - Exit & Experience Letters`
3. Right-click the folder → "Share"
4. Share with your service account email (found in the JSON key file, looks like `joyhr-drive-service@project-id.iam.gserviceaccount.com`)
5. Give it "Editor" permissions
6. Copy the Folder ID from the URL (e.g., `https://drive.google.com/drive/folders/FOLDER_ID_HERE`)

### Step 6: Configure Backend

1. **Place Service Account Key**:
   ```bash
   cd /Users/pravinraj/dev/joyhr/backend
   mkdir -p credentials
   mv ~/Downloads/joyhr-xxxxx.json credentials/service-account.json
   ```

2. **Update .env file**:
   ```bash
   cd /Users/pravinraj/dev/joyhr/backend
   nano .env
   ```
   
   Add these lines:
   ```env
   # Google Drive Configuration
   GOOGLE_SERVICE_ACCOUNT_PATH=credentials/service-account.json
   GOOGLE_DRIVE_FOLDER_ID=your_folder_id_here  # Optional: from Step 5
   ```

3. **Verify Installation**:
   ```bash
   source venv/bin/activate
   python -c "from app.services.google_drive import drive_service; print('✅ Google Drive service initialized')"
   ```

### Step 7: Test the Integration

1. **Start the backend server**:
   ```bash
   cd /Users/pravinraj/dev/joyhr/backend
   source venv/bin/activate
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Test letter creation**:
   - Log in as HR user
   - Navigate to Documents
   - Create a test letter request
   - Log in as Director
   - Approve the request
   - Check that PDF is uploaded to Google Drive
   - Click "View in Drive" button to open in browser

## 📁 File Structure

```
backend/
├── credentials/
│   └── service-account.json    # Google service account key (DO NOT COMMIT!)
├── app/
│   ├── services/
│   │   └── google_drive.py     # Google Drive service wrapper
│   └── routes/
│       └── letters.py          # Updated with Drive integration
└── .env                        # Environment variables (DO NOT COMMIT!)
```

## 🔒 Security Best Practices

### 1. Protect Service Account Key
```bash
# Add to .gitignore
echo "credentials/" >> .gitignore
echo ".env" >> .gitignore
```

### 2. Set Proper Permissions
```bash
chmod 600 credentials/service-account.json
```

### 3. Rotate Keys Regularly
- Generate new service account keys every 90 days
- Delete old keys from Google Cloud Console
- Update the credentials file in your backend

### 4. Monitor API Usage
- Check Google Cloud Console → "APIs & Services" → "Dashboard"
- Set up billing alerts
- Review API quotas

## 📊 How It Works

### PDF Upload Flow
```
1. Director approves letter request
   ↓
2. Backend generates PDF with ReportLab
   ↓
3. PDF uploaded to Google Drive via API
   ↓
4. Drive returns file_id and web_view_link
   ↓
5. Links stored in Firestore (letter_requests collection)
   ↓
6. Frontend displays "View in Drive" button
```

### PDF Download Flow
```
1. User clicks "Download PDF" button
   ↓
2. Backend retrieves file_id from Firestore
   ↓
3. Downloads PDF from Google Drive
   ↓
4. Streams PDF to user's browser
   ↓
5. Fallback: Regenerate if Drive download fails
```

## 🎨 Frontend Features

### New UI Elements
- **"View in Drive" button** - Opens PDF in Google Drive web viewer
- **Google Drive icon** - Visual indicator for cloud storage
- **Fallback handling** - Regenerates PDF if Drive is unavailable

### Updated LetterRequest Interface
```typescript
interface LetterRequest {
  // ... existing fields
  experience_letter_link?: string;    // Google Drive view link
  experience_file_id?: string;        // Drive file ID
  exit_letter_link?: string;
  exit_file_id?: string;
  pdfFiles?: Array<{                  // Full file metadata
    type: string;
    filename: string;
    file_id: string;
    web_view_link: string;
    download_link?: string;
  }>;
}
```

## 🔧 API Endpoints

### Updated Endpoints

#### POST `/api/letters/approve/{letter_id}`
**New behavior**: Uploads generated PDFs to Google Drive and stores links
```json
Response:
{
  "status": "approved",
  "experience_letter_link": "https://drive.google.com/file/d/...",
  "experience_file_id": "1abc...",
  "exit_letter_link": "https://drive.google.com/file/d/...",
  "exit_file_id": "1def...",
  "pdfFiles": [...]
}
```

#### GET `/api/letters/download/{letter_id}?letter_type=experience`
**New behavior**: Downloads from Google Drive with fallback to regeneration
- Query param `letter_type`: `'exit'` or `'experience'` (optional for 'both')
- Returns PDF stream from Drive or regenerates if unavailable

## 🚨 Troubleshooting

### Issue: "Google Drive service not initialized"
**Cause**: Service account file not found or invalid
**Solution**:
1. Check file path in .env: `GOOGLE_SERVICE_ACCOUNT_PATH`
2. Verify JSON file exists and is valid
3. Check file permissions: `ls -l credentials/`

### Issue: "Permission denied" when uploading
**Cause**: Service account doesn't have access to Drive folder
**Solution**:
1. Share the folder with service account email
2. Give "Editor" permissions
3. Or remove `GOOGLE_DRIVE_FOLDER_ID` to upload to root Drive

### Issue: PDF upload succeeds but "View in Drive" doesn't work
**Cause**: File permissions not set correctly
**Solution**: The service automatically makes files public (anyone with link), but check:
1. File permissions in Google Drive
2. Organization policies (may restrict sharing)

### Issue: Downloads are slow
**Cause**: Downloading from Drive takes time
**Solution**:
1. Consider implementing frontend caching
2. Use Drive's download_link for direct downloads
3. Pre-generate PDFs for frequently accessed letters

## 📈 Monitoring & Maintenance

### Check Storage Usage
```python
# Add to your backend monitoring script
from app.services.google_drive import drive_service

# Get storage quota
about = drive_service.service.about().get(fields="storageQuota").execute()
print(f"Used: {about['storageQuota']['usage']} bytes")
print(f"Limit: {about['storageQuota']['limit']} bytes")
```

### List All Letters in Drive
```python
# Query all letter PDFs
query = "mimeType='application/pdf' and name contains 'letter'"
results = drive_service.service.files().list(q=query, fields="files(id, name, createdTime)").execute()
files = results.get('files', [])
print(f"Total letters: {len(files)}")
```

### Cleanup Old Letters (Optional)
```python
# Delete letters older than 7 years (legal retention period)
from datetime import datetime, timedelta

cutoff_date = datetime.now() - timedelta(days=365*7)
# Implement deletion logic with caution
```

## 🎯 Next Steps (Optional Enhancements)

1. **Email Notifications**: Send Drive links to employees via email
2. **Batch Upload**: Upload multiple letters at once
3. **Custom Templates**: Store letter templates in Drive
4. **Digital Signatures**: Integrate DocuSign for signed letters
5. **Folder Organization**: Organize by department/year
6. **Analytics**: Track document views and downloads
7. **Backup**: Automatic backup to secondary storage

## 📚 Additional Resources

- [Google Drive API Documentation](https://developers.google.com/drive/api/v3/about-sdk)
- [Service Account Guide](https://cloud.google.com/iam/docs/service-accounts)
- [Python Client Library](https://github.com/googleapis/google-api-python-client)
- [Drive API Quotas](https://developers.google.com/drive/api/v3/about-quota)

## ✅ Verification Checklist

- [ ] Google Cloud project created
- [ ] Drive API enabled
- [ ] Service account created with key
- [ ] JSON key file downloaded and secured
- [ ] Drive folder created and shared with service account
- [ ] Backend .env configured with paths
- [ ] Dependencies installed (`google-api-python-client`, etc.)
- [ ] Service initialization successful
- [ ] Test letter uploaded to Drive
- [ ] "View in Drive" button works in frontend
- [ ] Download functionality works
- [ ] .gitignore updated to exclude credentials

---

**Status**: ✅ Google Drive Integration Complete
**Last Updated**: November 12, 2025
**Version**: 1.0.0
