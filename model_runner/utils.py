def ensure_function(module, name: str):
    if not hasattr(module, name):
        raise ValueError(f"no `{name}` function found")

    return getattr(module, name)
