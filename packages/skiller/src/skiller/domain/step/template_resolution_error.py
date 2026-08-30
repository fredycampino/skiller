class UnresolvedTemplateError(ValueError):
    """A template depends on runtime state that is not available yet."""
