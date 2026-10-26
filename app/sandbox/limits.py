from dataclasses import dataclass

@dataclass
class SandboxLimits:
    """Resource constraints and timeouts for project sandboxes."""
    cpu_quota: int = 100000          # 1 CPU core equivalent (in microseconds)
    cpu_period: int = 100000         # CPU CFS period
    mem_limit: str = "1g"            # Max memory usage (1 Gigabyte)
    network_timeout: int = 300       # Network timeout in seconds for operations
    idle_timeout_seconds: int = 1800 # 30 minutes of inactivity before reaper cleanup
    max_file_size_mb: int = 500      # Max workspace storage limit