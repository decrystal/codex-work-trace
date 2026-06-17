class CSGSError(Exception):
    """Base error for CSGS operations."""


class RunNotFoundError(CSGSError):
    def __init__(self, run_id: str):
        super().__init__(f"run not found: {run_id}")
        self.run_id = run_id


class RunAlreadyExistsError(CSGSError):
    def __init__(self, run_id: str):
        super().__init__(f"run already exists: {run_id}")
        self.run_id = run_id
