"""PrusaLink-specific exceptions."""


class PrusaLinkError(Exception):
    """Base exception for PrusaLink operations."""

    pass


class PrusaLinkConnectionError(PrusaLinkError):
    """Exception raised when connection to PrusaLink fails."""

    pass


class PrusaLinkAuthError(PrusaLinkError):
    """Exception raised when authentication with PrusaLink fails."""

    pass


class PrusaLinkUploadError(PrusaLinkError):
    """Exception raised when file upload to PrusaLink fails."""

    pass


class PrusaLinkConfigError(PrusaLinkError):
    """Exception raised when PrusaLink configuration is invalid."""

    pass
