from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import zipfile
import requests


@dataclass
class GridFileDownloadClient:
    base_url: str
    api_key: str

    def list_files(self, series_id: str) -> dict:
        url = f"{self.base_url.rstrip('/')}/file-download/list/{series_id}"
        r = requests.get(url, headers={"x-api-key": self.api_key}, timeout=60)
        r.raise_for_status()
        return r.json()

    def download_bytes(self, full_url: str) -> bytes:
        r = requests.get(full_url, headers={"x-api-key": self.api_key}, timeout=120)
        r.raise_for_status()
        return r.content

    def download_to(self, full_url: str, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(full_url, headers={"x-api-key": self.api_key}, stream=True, timeout=180) as r:
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