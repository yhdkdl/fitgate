"""
Unified file storage layer for FitGate platform (Sprint 4b).

Abstracts public assets (gym logos) and authenticated assets (member photos)
behind Django's storage interface. Supports Cloudinary and local FileSystemStorage fallback.
"""

import io
import os
import re
import uuid
from typing import Any, Tuple

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from PIL import Image

SAFE_FILENAME_REGEX = re.compile(r"^[a-zA-Z0-9_-]+\.(webp|jpg|jpeg|png)$")
ALLOWED_IMAGE_FORMATS = frozenset({"JPEG", "JPG", "PNG", "WEBP"})
MAX_IMAGE_SIZE = getattr(settings, "MAX_UPLOAD_SIZE_BYTES", 2 * 1024 * 1024)  # 2MB


def validate_and_process_image(
    uploaded_file,
    max_size_bytes: int = MAX_IMAGE_SIZE,
    max_dimensions: Tuple[int, int] = (800, 800),
) -> Tuple[ContentFile, str]:
    """
    Validate uploaded image and process it:
    - Enforces <= 2 MB file size limit.
    - Inspects file headers & structure via Pillow to ensure valid image.
    - Rejects non-image, corrupt, or unsupported formats.
    - Strips EXIF/metadata for user privacy.
    - Resizes image down to max_dimensions preserving aspect ratio.
    - Generates a cryptographically random filename.
    - Converts to optimized WebP format.

    Returns:
        (ContentFile, random_filename)
    """
    if not uploaded_file:
        raise ValidationError("No file was uploaded.")

    # 1. Size validation
    file_size = getattr(uploaded_file, "size", None)
    if file_size is None:
        uploaded_file.seek(0, os.SEEK_END)
        file_size = uploaded_file.tell()
        uploaded_file.seek(0)

    if file_size > max_size_bytes:
        max_mb = max_size_bytes // (1024 * 1024)
        raise ValidationError(f"File size exceeds maximum allowed {max_mb} MB limit.")

    # 2. Content & format validation using Pillow
    uploaded_file.seek(0)
    try:
        with Image.open(uploaded_file) as img:
            image_format = (img.format or "").upper()
            if image_format not in ALLOWED_IMAGE_FORMATS:
                raise ValidationError(
                    f"Unsupported image format '{image_format}'. Only JPEG, PNG, and WebP are allowed."
                )
            img_copy = img.copy()
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError("Uploaded file is not a valid image.") from exc

    # 3. Mode normalization & resizing
    if img_copy.mode in ("CMYK", "P", "LA"):
        img_copy = img_copy.convert("RGBA" if "A" in img_copy.mode else "RGB")
    elif img_copy.mode not in ("RGB", "RGBA"):
        img_copy = img_copy.convert("RGB")

    width, height = img_copy.size
    max_w, max_h = max_dimensions
    if width > max_w or height > max_h:
        img_copy.thumbnail(max_dimensions, Image.Resampling.LANCZOS)

    # 4. Save to in-memory buffer without metadata
    output_buffer = io.BytesIO()
    img_copy.save(output_buffer, format="WEBP", quality=85, method=6)
    output_buffer.seek(0)

    # 5. Cryptographically random filename
    random_filename = f"{uuid.uuid4().hex}.webp"
    content_file = ContentFile(output_buffer.getvalue(), name=random_filename)

    return content_file, random_filename


class FitGateStorage:
    """
    Unified storage abstraction for FitGate.

    - Member photos: saved as authenticated assets in per-gym paths:
      'gyms/<gym_id>/member_photos/<filename>'
    - Gym logos: saved as public assets in 'logos/<filename>'
    - Uses Cloudinary if credentials are configured in environment;
      otherwise falls back to local FileSystemStorage in MEDIA_ROOT.
    """

    def __init__(self):
        self._local_storage = None

    @property
    def is_cloudinary(self) -> bool:
        cloud_name = getattr(settings, "CLOUDINARY_CLOUD_NAME", "")
        api_key = getattr(settings, "CLOUDINARY_API_KEY", "")
        api_secret = getattr(settings, "CLOUDINARY_API_SECRET", "")
        return bool(cloud_name and api_key and api_secret)

    @property
    def local_storage(self) -> FileSystemStorage:
        current_location = str(settings.MEDIA_ROOT)
        if (
            self._local_storage is None
            or self._local_storage.location != current_location
        ):
            self._local_storage = FileSystemStorage(
                location=settings.MEDIA_ROOT,
                base_url=settings.MEDIA_URL,
            )
        return self._local_storage

    def _ensure_cloudinary_configured(self):
        import cloudinary

        cloudinary.config(
            cloud_name=getattr(settings, "CLOUDINARY_CLOUD_NAME", ""),
            api_key=getattr(settings, "CLOUDINARY_API_KEY", ""),
            api_secret=getattr(settings, "CLOUDINARY_API_SECRET", ""),
            secure=True,
        )

    def save_public_asset(self, relative_path: str, content_file: ContentFile) -> str:
        """
        Store a public asset (e.g. gym logo).
        Returns URL or storage path.
        """
        if self.is_cloudinary:
            self._ensure_cloudinary_configured()
            import cloudinary.uploader

            result = cloudinary.uploader.upload(
                content_file,
                public_id=os.path.splitext(relative_path)[0],
                resource_type="image",
                type="upload",
                overwrite=True,
            )
            return result.get("secure_url", result.get("url"))
        else:
            saved_name = self.local_storage.save(relative_path, content_file)
            return self.local_storage.url(saved_name)

    def save_authenticated_asset(
        self, relative_path: str, content_file: ContentFile
    ) -> str:
        """
        Store an authenticated/private asset (e.g. member photo).
        Returns internal relative path. The browser NEVER receives a direct Cloudinary URL.
        """
        if self.is_cloudinary:
            self._ensure_cloudinary_configured()
            import cloudinary.uploader

            cloudinary.uploader.upload(
                content_file,
                public_id=os.path.splitext(relative_path)[0],
                resource_type="image",
                type="authenticated",
                overwrite=True,
            )
            return relative_path
        else:
            return self.local_storage.save(relative_path, content_file)

    def get_authenticated_asset(self, relative_path: str) -> Tuple[Any, str]:
        """
        Retrieve binary stream and content_type of authenticated asset.
        """
        if self.is_cloudinary:
            self._ensure_cloudinary_configured()
            import urllib.request

            import cloudinary.utils

            signed_url, _ = cloudinary.utils.cloudinary_url(
                os.path.splitext(relative_path)[0],
                type="authenticated",
                sign_url=True,
            )
            req = urllib.request.urlopen(signed_url)
            data = req.read()
            return io.BytesIO(data), "image/webp"
        else:
            if not self.local_storage.exists(relative_path):
                raise FileNotFoundError(f"File {relative_path} does not exist.")
            file_obj = self.local_storage.open(relative_path, mode="rb")
            return file_obj, "image/webp"


_storage_instance = None


def get_storage() -> FitGateStorage:
    """Return the singleton instance of FitGateStorage."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = FitGateStorage()
    return _storage_instance


def save_member_photo(gym_id: Any, uploaded_file) -> str:
    """
    Validate, process, and save a member photo into gym-scoped authenticated storage.
    Path: gyms/<gym_id>/member_photos/<random_name>.webp
    """
    content_file, random_filename = validate_and_process_image(uploaded_file)
    relative_path = f"gyms/{gym_id}/member_photos/{random_filename}"
    storage = get_storage()
    storage.save_authenticated_asset(relative_path, content_file)
    return relative_path


def save_gym_logo(gym_id: Any, uploaded_file) -> str:
    """
    Validate, process, and save a gym logo into public storage.
    Path: logos/{gym_id}_{random_name}.webp
    """
    content_file, random_filename = validate_and_process_image(
        uploaded_file,
        max_dimensions=(500, 500),
    )
    relative_path = f"logos/{gym_id}_{random_filename}"
    storage = get_storage()
    return storage.save_public_asset(relative_path, content_file)


def get_authenticated_photo_stream(gym_id: Any, filename: str) -> Tuple[Any, str]:
    """
    Retrieve binary stream for an authenticated member photo.
    Enforces safe filename format to protect against path traversal attacks.
    """
    if not SAFE_FILENAME_REGEX.match(filename):
        raise ValidationError("Invalid filename format.")

    relative_path = f"gyms/{gym_id}/member_photos/{filename}"
    storage = get_storage()
    return storage.get_authenticated_asset(relative_path)
