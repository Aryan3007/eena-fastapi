import cloudinary.uploader
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.common.middleware.auth import get_current_user
from app.common.middleware.rate_limiter import limiter
from app.modules.user.models import User

router = APIRouter(prefix="/upload", tags=["Upload"])

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


@router.post("/image")
@limiter.limit("20/15minutes")
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
) -> dict:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")

    result = cloudinary.uploader.upload(
        content,
        folder="eena/images",
        resource_type="image",
    )

    return {
        "url": result["secure_url"],
        "publicId": result["public_id"],
    }


@router.post("/images")
@limiter.limit("20/15minutes")
async def upload_images(
    request: Request,
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
) -> dict:
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 images")

    results = []
    for file in files:
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"File {file.filename} is not an image")

        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File {file.filename} too large")

        result = cloudinary.uploader.upload(
            content,
            folder="eena/images",
            resource_type="image",
        )
        results.append({
            "url": result["secure_url"],
            "publicId": result["public_id"],
        })

    return {"images": results}


@router.post("/video")
@limiter.limit("20/15minutes")
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
) -> dict:
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="File must be a video")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large")

    result = cloudinary.uploader.upload(
        content,
        folder="eena/videos",
        resource_type="video",
    )

    # Generate thumbnail URL from Cloudinary
    thumbnail_url = result["secure_url"].replace("/upload/", "/upload/so_0,w_400,h_400,c_fill/").replace(
        ".mp4", ".jpg"
    ).replace(".mov", ".jpg").replace(".webm", ".jpg")

    return {
        "url": result["secure_url"],
        "publicId": result["public_id"],
        "thumbnailUrl": thumbnail_url,
    }
