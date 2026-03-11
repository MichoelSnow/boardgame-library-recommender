from __future__ import annotations

import logging
import mimetypes
import os
from dataclasses import dataclass
from typing import Optional

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

try:
    from ..common.logging_utils import build_log_handlers
except ImportError:
    from data_pipeline.src.common.logging_utils import build_log_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=build_log_handlers("r2_image_sync.log"),
)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif", "avif"}
CONTENT_TYPE_TO_EXTENSION = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/avif": "avif",
}


@dataclass(frozen=True)
class R2Config:
    endpoint_url: str
    access_key_id: str
    secret_access_key: str
    bucket_name: str
    region: str = "auto"
    public_base_url: Optional[str] = None

    @staticmethod
    def from_env() -> "R2Config":
        endpoint_url = os.getenv("R2_ENDPOINT_URL", "").strip()
        access_key_id = os.getenv("R2_ACCESS_KEY_ID", "").strip()
        secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
        bucket_name = os.getenv("R2_BUCKET_NAME", "").strip()
        region = os.getenv("R2_REGION", "auto").strip() or "auto"
        public_base_url = os.getenv("R2_PUBLIC_BASE_URL", "").strip() or None

        missing = []
        if not endpoint_url:
            missing.append("R2_ENDPOINT_URL")
        if not access_key_id:
            missing.append("R2_ACCESS_KEY_ID")
        if not secret_access_key:
            missing.append("R2_SECRET_ACCESS_KEY")
        if not bucket_name:
            missing.append("R2_BUCKET_NAME")

        if missing:
            raise ValueError(
                f"Missing required R2 environment variables: {', '.join(missing)}"
            )

        return R2Config(
            endpoint_url=endpoint_url,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            bucket_name=bucket_name,
            region=region,
            public_base_url=public_base_url,
        )


def _extension_from_url(image_url: Optional[str]) -> Optional[str]:
    if not image_url:
        return None
    guessed_type, _ = mimetypes.guess_type(image_url)
    if guessed_type:
        return _extension_from_content_type(guessed_type)
    filename = image_url.split("?")[0].split("#")[0].rsplit("/", 1)[-1]
    if "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext in ALLOWED_EXTENSIONS:
        return "jpg" if ext == "jpeg" else ext
    return None


def _extension_from_content_type(content_type: Optional[str]) -> Optional[str]:
    if not content_type:
        return None
    media_type = content_type.split(";", 1)[0].strip().lower()
    return CONTENT_TYPE_TO_EXTENSION.get(media_type)


def build_r2_image_key(
    bgg_id: int,
    *,
    image_url: Optional[str] = None,
    content_type: Optional[str] = None,
) -> str:
    if not isinstance(bgg_id, int) or bgg_id <= 0:
        raise ValueError(f"Invalid bgg_id for image key generation: {bgg_id}")

    extension = (
        _extension_from_content_type(content_type)
        or _extension_from_url(image_url)
        or "jpg"
    )
    return f"games/{bgg_id}.{extension}"


@retry(
    retry=retry_if_exception_type((requests.RequestException, TimeoutError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def download_image_content(
    image_url: str,
    *,
    timeout_seconds: int = 20,
    session: Optional[requests.Session] = None,
) -> tuple[bytes, Optional[str]]:
    client = session or requests
    response = client.get(image_url, timeout=timeout_seconds)
    response.raise_for_status()
    return response.content, response.headers.get("Content-Type")


class R2ImageSyncer:
    def __init__(self, config: R2Config):
        import boto3
        from botocore.config import Config
        from botocore.exceptions import BotoCoreError, ClientError

        self.config = config
        self._client_error_cls = ClientError
        self._boto_core_error_cls = BotoCoreError
        self.client = boto3.client(
            "s3",
            endpoint_url=config.endpoint_url,
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
            region_name=config.region,
            config=Config(signature_version="s3v4"),
        )

    @classmethod
    def from_env(cls) -> "R2ImageSyncer":
        return cls(R2Config.from_env())

    def object_exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.config.bucket_name, Key=key)
            return True
        except self._client_error_cls as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def existing_key_for_bgg_id(self, bgg_id: int) -> Optional[str]:
        """
        Return the first existing canonical image key for a game, or None.

        This lets sync paths skip origin downloads when an object already exists
        in R2 under any supported extension.
        """
        for extension in sorted(ALLOWED_EXTENSIONS):
            normalized_ext = "jpg" if extension == "jpeg" else extension
            key = f"games/{bgg_id}.{normalized_ext}"
            if self.object_exists(key):
                return key
        return None

    def list_existing_game_keys(
        self,
        *,
        prefix: str = "games/",
        max_keys: int = 1000,
    ) -> set[str]:
        """
        List existing object keys under the canonical games prefix.

        Returns a set of object keys (e.g., {"games/224517.jpg", ...}).
        """
        keys: set[str] = set()
        continuation_token: Optional[str] = None

        while True:
            kwargs = {
                "Bucket": self.config.bucket_name,
                "Prefix": prefix,
                "MaxKeys": max_keys,
            }
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token

            response = self.client.list_objects_v2(**kwargs)
            for obj in response.get("Contents", []):
                key = obj.get("Key")
                if key:
                    keys.add(key)

            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")
            if not continuation_token:
                break

        return keys

    @staticmethod
    def build_existing_bgg_id_map(keys: set[str]) -> dict[int, str]:
        """
        Build a map of bgg_id -> key from canonical keys.
        """
        existing: dict[int, str] = {}
        for key in keys:
            if not key.startswith("games/"):
                continue
            filename = key[len("games/") :]
            if "." not in filename:
                continue
            id_part = filename.rsplit(".", 1)[0]
            try:
                bgg_id = int(id_part)
            except ValueError:
                continue
            existing[bgg_id] = key
        return existing

    def upload_bytes(
        self,
        *,
        key: str,
        content: bytes,
        content_type: Optional[str],
        cache_control: str = "public, max-age=31536000, immutable",
    ) -> None:
        put_kwargs = {
            "Bucket": self.config.bucket_name,
            "Key": key,
            "Body": content,
            "CacheControl": cache_control,
        }
        if content_type:
            put_kwargs["ContentType"] = content_type.split(";", 1)[0].strip().lower()
        self.client.put_object(**put_kwargs)

    def sync_image_url(
        self,
        *,
        bgg_id: int,
        image_url: str,
        overwrite_existing: bool = False,
        session: Optional[requests.Session] = None,
    ) -> tuple[str, str]:
        if not overwrite_existing:
            existing_key = self.existing_key_for_bgg_id(bgg_id)
            if existing_key:
                return existing_key, "skipped_existing"

        image_bytes, content_type = download_image_content(image_url, session=session)
        key = build_r2_image_key(bgg_id, image_url=image_url, content_type=content_type)

        self.upload_bytes(key=key, content=image_bytes, content_type=content_type)
        return key, "uploaded"


def r2_config_available() -> bool:
    required_keys = [
        "R2_ENDPOINT_URL",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_BUCKET_NAME",
    ]
    return all(os.getenv(key, "").strip() for key in required_keys)


def is_retryable_r2_error(exc: Exception) -> bool:
    try:
        from botocore.exceptions import BotoCoreError, ClientError

        return isinstance(exc, (BotoCoreError, ClientError))
    except Exception:
        return False
