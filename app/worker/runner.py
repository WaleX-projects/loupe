import asyncio
import json
from strands.multiagent import Status, Swarm
from app.sandbox.workspace_manager import workspace_manager
from app.agents.swarm import build_swarm
from app.api.ws.pump import EventPump
from strands.sandbox.docker import DockerSandbox
from app.services.redis_client import redis_client

# In-memory store to keep active paused swarms across run and resume steps
_ACTIVE_SWARMS = {}

class TaskRunner:
    @staticmethod
    async def run_job(project_id: str, prompt: str):
        pump = EventPump(project_id)
        
        try:
            await pump.emit("job_started", f"Provisioning workspace for project {project_id}...")

            # 1. Provision Sandbox & Container
            container_id, host_path = workspace_manager.provision(project_id)
            await pump.emit("sandbox_ready", "Container and volume provisioned.", {"container_id": container_id})

            # 2. Bind Strands DockerSandbox
            sandbox = DockerSandbox(
                container_id,
                working_dir="/workspace",
                user="1000:1000",
            )

            # 3. Build Swarm
            swarm = build_swarm(sandbox)
            
            # Cache the active swarm instance for resumption
            _ACTIVE_SWARMS[project_id] = swarm

            await pump.emit("agents_active", "Swarm agents loaded and initialized.")
            await pump.emit("execution_running", "Agent swarm workflow started...")

            # 4. Execute swarm
            result = swarm(prompt)

            # 5. Handle Interruption
            if result.status == Status.INTERRUPTED:
                interrupts_data = []
                for interrupt in result.interrupts:
                    await redis_client.set(f"project:interrupt_id:{project_id}", interrupt.id)
                    interrupts_data.append({
                        "interruptId": interrupt.id,
                        "name": interrupt.name,
                        "reason": interrupt.reason
                    })
                
                await pump.emit("job_interrupted", "Swarm execution paused for human approval.", {
                    "interrupts": interrupts_data,
                    "status": "Status.INTERRUPTED"
                })
                return

            # Clear cache if completed without interruption
            _ACTIVE_SWARMS.pop(project_id, None)

            await pump.emit("job_completed", "Swarm execution completed successfully.", {
                "status": getattr(result, "status", "SUCCESS")
            })

        except Exception as e:
            _ACTIVE_SWARMS.pop(project_id, None)
            await pump.emit("job_failed", f"An error occurred during execution: {str(e)}")
            raise e

    @staticmethod
    async def resume_job(project_id: str, user_input: str):
        pump = EventPump(project_id)
        
        try:
            await pump.emit("job_resumed", f"Resuming job for project {project_id} with user response...")

            # 1. Retrieve pending interrupt ID from Redis
            interrupt_id = await redis_client.get(f"project:interrupt_id:{project_id}")
            if not interrupt_id:
                raise ValueError(f"No pending interrupt found for project {project_id}")
            
            if isinstance(interrupt_id, bytes):
                interrupt_id = interrupt_id.decode("utf-8")

            # 2. Retrieve the active paused swarm instance from memory
            swarm = _ACTIVE_SWARMS.get(project_id)
            if not swarm:
                raise ValueError(f"No active swarm session found in memory for project {project_id}. Worker may have restarted.")

            # 3. Format the interrupt response payload required by Strands
            responses = [{
                "interruptResponse": {
                    "interruptId": interrupt_id,
                    "response": user_input,
                }
            }]

            # 4. Resume execution by passing responses back into the existing swarm instance
            result = swarm(responses)

            # 5. Check if it hit another interrupt or completed
            if result.status == Status.INTERRUPTED:
                interrupts_data = []
                for interrupt in result.interrupts:
                    await redis_client.set(f"project:interrupt_id:{project_id}", interrupt.id)
                    interrupts_data.append({
                        "interruptId": interrupt.id,
                        "name": interrupt.name,
                        "reason": interrupt.reason
                    })
                
                await pump.emit("job_interrupted", "Swarm paused again for further approval.", {
                    "interrupts": interrupts_data,
                    "status": "Status.INTERRUPTED"
                })
                return

            # Clean up cache and Redis key upon successful completion
            _ACTIVE_SWARMS.pop(project_id, None)
            await redis_client.delete(f"project:interrupt_id:{project_id}")

            await pump.emit("job_completed", "Resumed swarm execution completed successfully.", {
                "status": getattr(result, "status", "SUCCESS")
            })

        except Exception as e:
            _ACTIVE_SWARMS.pop(project_id, None)
            await pump.emit("job_failed", f"An error occurred while resuming: {str(e)}")
            raise e