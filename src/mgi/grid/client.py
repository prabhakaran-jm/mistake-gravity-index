from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
import requests


@dataclass
class GridGraphQLClient:
    url: str
    api_key: str

    def query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        headers = {
            "x-api-key": self.api_key,
            "content-type": "application/json",
        }
        payload = {"query": query, "variables": variables or {}}

        r = requests.post(self.url, json=payload, headers=headers, timeout=60)
        r.raise_for_status()
        data = r.json()

        if "errors" in data and data["errors"]:
            raise RuntimeError(f"GRID GraphQL errors: {data['errors']}")

        if "data" not in data:
            raise RuntimeError(f"Unexpected response: {data}")

        return data["data"]