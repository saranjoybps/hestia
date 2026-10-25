"""
Google Drive Service for document storage
"""
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from google.oauth2 import service_account
from typing import Optional
import os
import json
from io import BytesIO
from app.config import get_settings

class GoogleDriveService:
    """Service for managing files in Google Drive"""
    
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    
    def __init__(self):
        """Initialize Google Drive service with service account credentials"""
        # Load service account credentials from settings
        settings = get_settings()
        credentials_path = settings.firebase_credentials_path
        
        try:
            if settings.firebase_credentials:
                credential_info = json.loads(settings.firebase_credentials)
                self.credentials = service_account.Credentials.from_service_account_info(
                    credential_info,
                    scopes=self.SCOPES
                )
            else:
                self.credentials = service_account.Credentials.from_service_account_file(
                    credentials_path,
                    scopes=self.SCOPES
                )
            self.service = build('drive', 'v3', credentials=self.credentials)
            self.folder_id = settings.google_drive_folder_id if settings.google_drive_folder_id else None
        except Exception as e:
            print(f"Warning: Google Drive initialization failed: {e}")
            print("PDF files will be generated but not uploaded to Drive")
            self.service = None
            self.folder_id = None
    
    def upload_pdf(
        self, 
        file_buffer: BytesIO, 
        filename: str, 
        mime_type: str = 'application/pdf'
    ) -> Optional[dict]:
        """
        Upload a PDF file to Google Drive
        
        Args:
            file_buffer: BytesIO buffer containing the PDF data
            filename: Name for the file in Google Drive
            mime_type: MIME type of the file
            
        Returns:
            dict with file_id and web_view_link, or None if upload fails
        """
        if not self.service:
            print("Google Drive service not initialized")
            return None
        
        try:
            file_metadata = {
                'name': filename,
                'mimeType': mime_type
            }
            
            # Add folder parent if specified
            if self.folder_id:
                file_metadata['parents'] = [self.folder_id]
            
            # Prepare media upload
            file_buffer.seek(0)  # Reset buffer position
            media = MediaInMemoryUpload(
                file_buffer.read(),
                mimetype=mime_type,
                resumable=True
            )
            
            # Upload file
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink, webContentLink'
            ).execute()
            
            return {
                'file_id': file.get('id'),
                'web_view_link': file.get('webViewLink'),
                'download_link': file.get('webContentLink')
            }
            
        except Exception as e:
            print(f"Error uploading to Google Drive: {e}")
            return None
    
    def delete_file(self, file_id: str) -> bool:
        """
        Delete a file from Google Drive
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            True if successful, False otherwise
        """
        if not self.service:
            return False
        
        try:
            self.service.files().delete(fileId=file_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting file from Google Drive: {e}")
            return False
    
    def get_file(self, file_id: str) -> Optional[BytesIO]:
        """
        Download a file from Google Drive
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            BytesIO buffer with file content, or None if download fails
        """
        if not self.service:
            return None
        
        try:
            self.restrict_public_access(file_id)
            request = self.service.files().get_media(fileId=file_id)
            file_buffer = BytesIO()
            
            # Download file in chunks
            from googleapiclient.http import MediaIoBaseDownload
            downloader = MediaIoBaseDownload(file_buffer, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file_buffer.seek(0)
            return file_buffer
            
        except Exception as e:
            print(f"Error downloading file from Google Drive: {e}")
            return None

    def restrict_public_access(self, file_id: str) -> bool:
        """Remove legacy anyone-with-link permissions from an application file."""
        if not self.service:
            return False
        try:
            permissions = self.service.permissions().list(fileId=file_id, fields='permissions(id,type)').execute().get('permissions', [])
            for permission in permissions:
                if permission.get('type') == 'anyone':
                    self.service.permissions().delete(fileId=file_id, permissionId=permission['id']).execute()
            return True
        except Exception as e:
            print(f"Error restricting document permissions: {e}")
            return False
    
    def create_folder(self, folder_name: str, parent_folder_id: Optional[str] = None) -> Optional[str]:
        """
        Create a folder in Google Drive
        
        Args:
            folder_name: Name of the folder
            parent_folder_id: Optional parent folder ID
            
        Returns:
            Folder ID if successful, None otherwise
        """
        if not self.service:
            return None
        
        try:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            if parent_folder_id:
                file_metadata['parents'] = [parent_folder_id]
            
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            
            return folder.get('id')
            
        except Exception as e:
            print(f"Error creating folder in Google Drive: {e}")
            return None

# Global instance
drive_service = GoogleDriveService()
