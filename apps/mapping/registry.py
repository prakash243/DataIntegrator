"""
Mapping function registry.

All available mapping functions are registered here with a stable ID,
the callable function, and a production flag.

Registry structure:
    - id: Stable, manually assigned ID (never changes)
    - function: The mapper function
    - production: True = available in production, False = staging/development only
"""

from .maps.csv_to_json import csv_to_json_mapper
from .maps.csv_to_json_file import csv_to_json_file_mapper
from .maps.json_to_csv import json_to_csv_mapper
from .maps.json_to_csv_file import json_to_csv_file_mapper

MAPPING_REGISTRY = {
    "csv_to_json": {
        "id": 1,
        "function": csv_to_json_mapper,
        "production": True,
    },
    "json_to_csv": {
        "id": 2,
        "function": json_to_csv_mapper,
        "production": True,
    },
    "csv_to_json_file": {
        "id": 3,
        "function": csv_to_json_file_mapper,
        "production": True,
    },
    "json_to_csv_file": {
        "id": 4,
        "function": json_to_csv_file_mapper,
        "production": True,
    },
}


def _validate_registry():
    """Ensure all map IDs are unique. Raises error on startup if duplicates found."""
    seen_ids = {}
    for name, entry in MAPPING_REGISTRY.items():
        map_id = entry["id"]
        if map_id in seen_ids:
            raise ValueError(
                f"Duplicate map ID {map_id}: '{name}' and '{seen_ids[map_id]}' have the same ID"
            )
        seen_ids[map_id] = name


_validate_registry()
