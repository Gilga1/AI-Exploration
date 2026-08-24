class HarnessError(Exception):
    """Base error for harness operations."""


class RegistryCollisionError(HarnessError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Capability name already registered: {name!r}")
        self.name = name


class UnresolvedDependencyError(HarnessError):
    def __init__(self, capability: str, missing: set[str]) -> None:
        super().__init__(
            f"Capability {capability!r} requires tools that are not registered: {sorted(missing)}"
        )
        self.capability = capability
        self.missing = missing


class BootstrapValidationError(HarnessError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("Bootstrap validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
        self.errors = errors
