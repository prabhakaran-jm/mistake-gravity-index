from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import requests


@dataclass
class BaseGridClient:
    api_key: str
    base_url: str
    timeout_s: int = 30
    session: requests.Session = field(init=False)

    def __post_init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"x-api-key": self.api_key})

    def get(self, path: str, params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> requests.Response:
        url = self.base_url.rstrip("/") + "/" + path.lstrip("/")
        timeout = kwargs.pop("timeout", self.timeout_s)
        r = self.session.get(url, params=params, timeout=timeout, **kwargs)
        r.raise_for_status()
        return r

    def post_json(self, path: str, payload: Dict[str, Any], **kwargs: Any) -> requests.Response:
        url = self.base_url.rstrip("/") + "/" + path.lstrip("/")
        timeout = kwargs.pop("timeout", self.timeout_s)
        r = self.session.post(url, json=payload, timeout=timeout, **kwargs)
        r.raise_for_status()
        return r
