class BrowserError(Exception):
    pass


class BrowserNotStartedError(BrowserError):
    def __init__(self, message: str = "Browser not started. Call start() first."):
        super().__init__(message)


class BrowserAlreadyStartedError(BrowserError):
    def __init__(self, message: str = "Browser already started."):
        super().__init__(message)


class ExecutionError(Exception):
    pass


class SecurityViolation(ExecutionError):
    def __init__(self, message: str = "Security violation detected."):
        super().__init__(message)


class CommandTimeoutError(ExecutionError):
    def __init__(self, timeout: float):
        super().__init__(f"Command timed out after {timeout}s")


class SessionError(Exception):
    pass


class SessionNotFoundError(SessionError):
    def __init__(self, session_id: str):
        super().__init__(f"Session '{session_id}' not found")
