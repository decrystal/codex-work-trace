class CSGSError(Exception):
    """Base error for CSGS operations."""


class SessionNotFoundError(CSGSError):
    def __init__(self, session_id: str):
        super().__init__(f"session not found: {session_id}")
        self.session_id = session_id


class SessionAlreadyExistsError(CSGSError):
    def __init__(self, session_id: str):
        super().__init__(f"session already exists: {session_id}")
        self.session_id = session_id
