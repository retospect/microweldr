"""PrusaLink-specific exceptions."""


class PrusaLinkError(Exception):
    """Base exception for PrusaLink operations."""

    pass


class PrusaLinkConnectionError(PrusaLinkError):
    """Raised when connection to PrusaLink fails."""

    pass


class PrusaLinkValidationError(PrusaLinkError):
    """Raised when command parameters are invalid."""

    pass


class PrusaLinkOperationError(PrusaLinkError):
    """Raised when a printer operation fails or is rejected."""

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


class PrusaLinkFileError(PrusaLinkError):
    """Exception raised when file operations fail."""

    pass


class PrusaLinkJobError(PrusaLinkError):
    """Exception raised when print job operations fail."""

    pass
