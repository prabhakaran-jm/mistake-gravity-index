from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    grid_api_key: str
    grid_central_data_url: str


def get_settings() -> Settings:
    api_key = os.getenv("GRID_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GRID_API_KEY is not set. Put it in your .env file.")

    central_url = os.getenv("GRID_CENTRAL_DATA_URL", "https://api-op.grid.gg/central-data/graphql").strip()

    return Settings(
        grid_api_key=api_key,
        grid_central_data_url=central_url,
    )