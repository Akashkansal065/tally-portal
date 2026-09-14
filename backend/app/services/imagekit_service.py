"""
ImageKit Service
Handles uploading and deleting customer owner portraits and shop photos in dedicated folders.
"""
import urllib.request
import urllib.parse
import base64
import json
from typing import Optional, Dict, Any, List
from fastapi import HTTPException
from app.core.config import settings


def upload_customer_photo(
    file_base64: str,
    file_name: str,
    folder: str,
    tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Upload a base64 encoded photo to ImageKit under a dedicated folder.
    e.g. folder='/customers/ledger_42' or '/customers/ledger_42/shop'
    """
    if not settings.IMAGEKIT_PRIVATE_KEY:
        raise HTTPException(
            status_code=500,
            detail="ImageKit private key is not configured in backend environment."
        )

    # Clean base64 header if present (e.g. data:image/jpeg;base64,...)
    clean_b64 = file_base64
    if "," in clean_b64:
        clean_b64 = clean_b64.split(",", 1)[1]

    auth_str = f"{settings.IMAGEKIT_PRIVATE_KEY}:"
    auth_header = base64.b64encode(auth_str.encode()).decode()

    payload = {
        "file": clean_b64,
        "fileName": file_name,
        "folder": folder,
        "useUniqueFileName": "true",
    }
    if tags:
        payload["tags"] = ",".join(tags)

    data = urllib.parse.urlencode(payload).encode("utf-8")

    req = urllib.request.Request(
        "https://upload.imagekit.io/api/v1/files/upload",
        data=data,
        headers={
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return {
                "file_id": res_data.get("fileId"),
                "name": res_data.get("name"),
                "url": res_data.get("url"),
                "thumbnail_url": res_data.get("thumbnailUrl") or res_data.get("url"),
                "file_path": res_data.get("filePath"),
            }
    except urllib.error.HTTPError as he:
        error_body = he.read().decode("utf-8") if he.fp else str(he)
        print(f"ImageKit HTTP error {he.code}: {error_body}")
        raise HTTPException(
            status_code=502,
            detail=f"ImageKit storage error: {error_body}"
        )
    except Exception as e:
        print(f"ImageKit upload exception: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload photo to ImageKit: {str(e)}"
        )


def delete_imagekit_file(file_id: str) -> bool:
    """
    Delete a file from ImageKit by fileId to maintain storage hygiene.
    """
    if not settings.IMAGEKIT_PRIVATE_KEY or not file_id:
        return False

    auth_str = f"{settings.IMAGEKIT_PRIVATE_KEY}:"
    auth_header = base64.b64encode(auth_str.encode()).decode()

    req = urllib.request.Request(
        f"https://api.imagekit.io/v1/files/{file_id}",
        headers={"Authorization": f"Basic {auth_header}"},
        method="DELETE"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status in (200, 204)
    except Exception as e:
        print(f"Failed to delete file {file_id} from ImageKit: {e}")
        return False
