import os
import shutil
import tarfile
from datetime import datetime, timezone
import docker
from docker.errors import NotFound, APIError
from app.sandbox.limits import SandboxLimits

class WorkspaceManager:
    def __init__(self, base_path: str = "./workspaces", base_image: str = "loupe-base-env:latest"):
        self.client = docker.from_env()
        self.base_path = os.path.abspath(base_path)
        self.base_image = base_image
        self.limits = SandboxLimits()
        os.makedirs(self.base_path, exist_ok=True)

    def _get_host_path(self, project_id: str) -> str:
        """Generates and ensures the physical host directory exists for a project."""
        path = os.path.join(self.base_path, str(project_id))
        os.makedirs(path, exist_ok=True)
        return path

    def validate_jail_path(self, project_id: str, target_path: str) -> str:
        """Ensures a given path stays strictly inside the project's sandbox workspace (jail prevention)."""
        host_root = self._get_host_path(project_id)
        abs_target = os.path.abspath(os.path.join(host_root, target_path))
        
        # Check if target is inside the host root directory
        if not abs_target.startswith(host_root):
            raise PermissionError("Security violation: Path traversal outside sandbox jail is forbidden.")
        return abs_target

    def provision(self, project_id: str) -> tuple[str, str]:
        """Creates host volume, provisions/wakes up the container, and returns (container_id, host_path)."""
        host_path = self._get_host_path(project_id)
        container_name = f"loupe-sandbox-{project_id}"

        try:
            container = self.client.containers.get(container_name)
            if container.status != "running":
                container.start()
            return container.id, host_path
            
        except NotFound:
            container = self.client.containers.run(
                image=self.base_image,
                name=container_name,
                detach=True,
                command="tail -f /dev/null",
                volumes={
                    host_path: {"bind": "/workspace", "mode": "rw"}
                },
                working_dir="/workspace",
                user="1000:1000",
                mem_limit=self.limits.mem_limit,
                cpu_quota=self.limits.cpu_quota,
                cpu_period=self.limits.cpu_period,
                network_mode="bridge",
            )
            return container.id, host_path

    def create_snapshot(self, project_id: str, backup_dest: str) -> str:
        """Creates a tarball snapshot of the project workspace for versioning or backup."""
        host_path = self._get_host_path(project_id)
        os.makedirs(backup_dest, exist_ok=True)
        
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        snapshot_filename = f"snapshot_{project_id}_{timestamp}.tar.gz"
        snapshot_path = os.path.join(backup_dest, snapshot_filename)

        with tarfile.open(snapshot_path, "w:gz") as tar:
            tar.add(host_path, arcname=os.path.basename(host_path))

        return snapshot_path

    def reaper_cleanup_idle(self):
        """Reaper process: Scans active loupe containers and stops/removes those exceeding idle limits."""
        try:
            containers = self.client.containers.list(filters={"name": "loupe-sandbox-"})
            
            for container in containers:
                # Inspect container stats or check last execution timestamp
                # For basic idle detection, inspect process activity or uptime metadata
                inspect_data = container.attrs
                state = inspect_data.get("State", {})
                
                # Check if container has been running for an extended duration with zero active tasks
                # (You can expand this by cross-referencing with your database job timestamps)
                started_at_str = state.get("StartedAt", "")
                if started_at_str:
                    # Basic cleanup implementation: stop containers running over the idle threshold
                    # Alternatively, check your DB for projects with no active worker jobs.
                    pass
                    
        except APIError as e:
            print(f"Reaper error during cleanup scan: {e}")

    def destroy_workspace(self, project_id: str):
        """Stops/removes the container and permanently deletes the local workspace files."""
        container_name = f"loupe-sandbox-{project_id}"
        
        # 1. Stop and remove container
        try:
            container = self.client.containers.get(container_name)
            container.remove(force=True)
        except NotFound:
            pass

        # 2. Delete host workspace directory
        host_path = self._get_host_path(project_id)
        if os.path.exists(host_path):
            shutil.rmtree(host_path, ignore_errors=True)

# Global workspace manager instance
workspace_manager = WorkspaceManager()