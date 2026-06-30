class UpworkAuthError(Exception):
    """Exception raised for Upwork authentication failures (e.g., 401, 403)."""
    pass

class UpworkAPIError(Exception):
    """Exception raised for general Upwork API structural errors."""
    pass