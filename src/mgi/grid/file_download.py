from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import zipfile
from mgi.grid.base_client import BaseGridClient


@dataclass
class GridFileDownloadClient(BaseGridClient):
    def list_files(self, series_id: str) -> dict:
        path = f"file-download/list/{series_id}"
        r = self.get(path, timeout=60)
        return r.json()

    def download_bytes(self, full_url: str) -> bytes:
        # Since full_url is provided, we might bypass the base_url logic in get() 
        # but BaseGridClient.get joins paths. 
        # Actually, full_url might be different from base_url.
        # Looking at original code: requests.get(full_url, ...)
        # If full_url starts with http, we should probably handle it.
        r = self.session.get(full_url, timeout=120)
        r.raise_for_status()
        return r.content

    def download_to(self, full_url: str, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with self.session.get(full_url, stream=True, timeout=180) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
        return out_path

    @staticmethod
    def unzip_first_jsonl(zip_path: Path, out_jsonl_path: Path) -> Path:
        out_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            jsonl_names = [n for n in zf.namelist() if n.endswith(".jsonl")]
            if not jsonl_names:
                raise RuntimeError(f"No .jsonl found inside zip: {zip_path.name}")
            name = jsonl_names[0]
            with zf.open(name) as src, open(out_jsonl_path, "wb") as dst:
                dst.write(src.read())
        return out_jsonl_path

    @staticmethod
    def pretty_save_json(obj: dict, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(obj, indent=2), encoding="utf-8")
        return out_path