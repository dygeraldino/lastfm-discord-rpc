class DomainError(Exception):
    pass


class ProviderError(DomainError):
    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error


class PublisherError(DomainError):
    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error


class ConfigurationError(DomainError):
    pass


class TrackNotPlayingError(DomainError):
    pass