"""
Chunked Upload for STT - Experimental
Attempts to reduce upload latency by streaming upload to fal.ai CDN
"""
import httpx
import tempfile
import os
from typing import Optional


class ChunkedUploader:
    """
    Handles chunked uploads to fal.ai CDN
    Note: Requires fal.ai to support resumable/chunked uploads
    """
    
    def __init__(self, chunk_size: int = 32768):
        """
        Initialize chunked uploader
        
        Args:
            chunk_size: Size of each upload chunk (default: 32KB)
        """
        self.chunk_size = chunk_size
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    async def initiate_upload(self, file_size: int) -> Optional[str]:
        """
        Initiate a chunked upload session with fal.ai
        Returns upload URL or None if not supported
        
        Note: This is theoretical - fal_client.upload_file() may not expose
        chunked upload endpoints. This would require direct CDN API access.
        """
        # TODO: Check if fal.ai exposes chunked upload API
        # For now, this is a placeholder
        return None
    
    async def upload_chunk(self, 
                          upload_url: str, 
                          chunk: bytes, 
                          offset: int, 
                          total_size: int) -> bool:
        """
        Upload a single chunk
        
        Args:
            upload_url: URL to upload to
            chunk: Chunk data
            offset: Byte offset in file
            total_size: Total file size
            
        Returns:
            True if successful
        """
        try:
            headers = {
                "Content-Range": f"bytes {offset}-{offset + len(chunk) - 1}/{total_size}",
                "Content-Type": "application/octet-stream"
            }
            
            response = await self.http_client.put(
                upload_url,
                content=chunk,
                headers=headers
            )
            
            return response.status_code in (200, 201, 204)
            
        except Exception as e:
            print(f"⚠️ Chunked upload error: {e}")
            return False
    
    async def upload_file_chunked(self, audio_data: bytes) -> Optional[str]:
        """
        Upload file in chunks
        
        Args:
            audio_data: Audio bytes to upload
            
        Returns:
            URL of uploaded file, or None if failed
        """
        total_size = len(audio_data)
        
        # Initiate upload
        upload_url = await self.initiate_upload(total_size)
        if not upload_url:
            print("⚠️ Chunked upload not supported by fal.ai, using standard upload")
            return None
        
        print(f"📤 Starting chunked upload ({total_size} bytes in {self.chunk_size}B chunks)")
        
        # Upload chunks
        offset = 0
        while offset < total_size:
            chunk_end = min(offset + self.chunk_size, total_size)
            chunk = audio_data[offset:chunk_end]
            
            success = await self.upload_chunk(upload_url, chunk, offset, total_size)
            if not success:
                print(f"❌ Failed to upload chunk at offset {offset}")
                return None
            
            offset = chunk_end
            progress = (offset / total_size) * 100
            print(f"⬆️ Upload progress: {progress:.1f}%")
        
        print("✅ Chunked upload complete")
        return upload_url
    
    async def cleanup(self):
        """Close HTTP client"""
        await self.http_client.aclose()


# Note: Currently fal.ai upload_file() is a black box
# To implement chunked upload, we'd need:
# 1. Direct access to fal.ai CDN upload endpoints
# 2. Support for multipart/resumable uploads
# 3. OR use a different upload strategy (S3, GCS, etc.)

# For now, this optimization is THEORETICAL and cannot be implemented
# without fal.ai API changes or using alternative upload methods.

# RECOMMENDATION: Skip this optimization for Phase 1
# The gains (~0.5s) don't justify the complexity without API support
