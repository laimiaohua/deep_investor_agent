

def get_api_key_from_state(state: dict, api_key_name: str) -> str:
    """Get an API key from the state object."""
    if state and state.get("metadata", {}).get("request"):
        request = state["metadata"]["request"]
        if hasattr(request, 'api_keys') and request.api_keys:
            return request.api_keys.get(api_key_name)
    return None


def get_use_openbb_from_state(state: dict) -> bool:
    """Get use_openbb configuration from the state object.
    
    Returns True if OpenBB should be used as primary data source, False otherwise.
    Defaults to False if not configured.
    """
    if state and state.get("metadata", {}).get("request"):
        request = state["metadata"]["request"]
        if hasattr(request, 'use_openbb'):
            return bool(request.use_openbb)
    # 也可以从环境变量读取
    import os
    return os.environ.get("USE_OPENBB", "false").lower() == "true"