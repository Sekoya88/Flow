from __future__ import annotations

from pathlib import PurePosixPath
from typing import Optional

import yaml


class ObsidianCloudVaultService:
    """S3-compatible vault backend. Works with AWS S3, Cloudflare R2, and MinIO."""

    def __init__(self, bucket: str, endpoint_url: Optional[str] = None) -> None:
        self.bucket = bucket
        self.endpoint_url = endpoint_url

    def _session(self):
        import aioboto3
        return aioboto3.Session()

    def _render_note(self, content: str, frontmatter: dict) -> str:
        if frontmatter:
            fm_str = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False)
            return f"---\n{fm_str}---\n\n{content}"
        return content

    def _key(self, workspace_id: str, path: str) -> str:
        return str(PurePosixPath(workspace_id) / path)

    async def create_note(
        self,
        path: str,
        content: str,
        frontmatter: dict | None = None,
        workspace_id: str = "default",
    ) -> str:
        key = self._key(workspace_id, path)
        body = self._render_note(content, frontmatter or {}).encode("utf-8")
        async with self._session().client("s3", endpoint_url=self.endpoint_url) as s3:
            await s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=body,
                ContentType="text/markdown",
                Metadata={"workspace_id": workspace_id},
            )
        return f"s3://{self.bucket}/{key}"

    async def append_note(self, path: str, content: str, workspace_id: str = "default") -> bool:
        key = self._key(workspace_id, path)
        async with self._session().client("s3", endpoint_url=self.endpoint_url) as s3:
            try:
                obj = await s3.get_object(Bucket=self.bucket, Key=key)
                existing = (await obj["Body"].read()).decode("utf-8")
                await s3.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=(existing + f"\n{content}").encode("utf-8"),
                    ContentType="text/markdown",
                )
                return True
            except Exception:
                return False

    async def read_note(self, path: str, workspace_id: str = "default") -> str:
        key = self._key(workspace_id, path)
        async with self._session().client("s3", endpoint_url=self.endpoint_url) as s3:
            try:
                obj = await s3.get_object(Bucket=self.bucket, Key=key)
                return (await obj["Body"].read()).decode("utf-8")
            except Exception:
                return ""

    async def list_notes(self, prefix: str = "", workspace_id: str = "default") -> list[str]:
        key_prefix = self._key(workspace_id, prefix)
        async with self._session().client("s3", endpoint_url=self.endpoint_url) as s3:
            paginator = s3.get_paginator("list_objects_v2")
            keys: list[str] = []
            async for page in paginator.paginate(Bucket=self.bucket, Prefix=key_prefix):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"].replace(f"{workspace_id}/", "", 1))
            return keys
