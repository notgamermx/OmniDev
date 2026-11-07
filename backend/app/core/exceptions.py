class ApplicationError(Exception):
    """Base exception for expected application-level failures."""


class ConfigurationError(ApplicationError):
    pass


class DatabaseError(ApplicationError):
    pass


class IntegrationError(ApplicationError):
    pass
