from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
from mgi.grid.base_client import BaseGridClient


@dataclass
class GridGraphQLClient(BaseGridClient):
    def query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {"query": query, "variables": variables or {}}
        # We don't need to specify headers here as BaseGridClient handles x-api-key
        # and we can use post_json from BaseGridClient
        r = self.post_json("", payload=payload, timeout=60)
        data = r.json()

        if "errors" in data and data["errors"]:
            raise RuntimeError(f"GRID GraphQL errors: {data['errors']}")

        if "data" not in data:
            raise RuntimeError(f"Unexpected response: {data}")

        return data["data"]