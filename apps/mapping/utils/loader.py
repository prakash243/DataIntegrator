from apps.mapping.registry import MAPPING_REGISTRY


def get_mapping_function(key: str):
    """
    Get a mapping function by its registry key.

    Args:
        key: The registry key/name of the mapping

    Returns:
        The mapper function

    Raises:
        ValueError: If the key is not found in the registry
    """
    if key not in MAPPING_REGISTRY:
        raise ValueError(f"Mapping key '{key}' not found in registry.")
    return MAPPING_REGISTRY[key]["function"]
