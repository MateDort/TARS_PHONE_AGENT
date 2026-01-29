"""Docker Sandbox for TARS Programming Agent.
Allows for safe execution of code and capture of outputs.
"""
import logging
import asyncio
from typing import Optional, Dict
import subprocess # For calling docker CLI if python-docker lib not present, or wrapper

logger = logging.getLogger(__name__)

class DockerSandbox:
    """Manages ephemeral Docker containers for code execution."""

    def __init__(self, image: str = "python:3.11-slim"):
        self.image = image
        self.container_id: Optional[str] = None
        self.is_active = False

    async def start(self):
        """Start the sandbox container."""
        # Note: In a real deploy we'd use 'docker run -d -t ...'
        # For this implementation plan, we'll shell out to docker command
        try:
            cmd = [
                "docker", "run", "-d", "-t", "--rm",
                "--name", "tars_sandbox_instance",
                self.image
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                self.container_id = stdout.decode().strip()
                self.is_active = True
                logger.info(f"Sandbox started with ID: {self.container_id}")
                return True
            else:
                logger.error(f"Failed to start sandbox: {stderr.decode()}")
                return False
        except Exception as e:
            logger.error(f"Docker start error: {e}")
            return False

    async def execute_code(self, code: str, filename: str = "script.py") -> Dict[str, str]:
        """Write code to file in container and execute it."""
        if not self.is_active or not self.container_id:
            return {"error": "Sandbox not active"}

        # 1. Write file
        # Echo code into file inside container? 
        # Easier to write local temp file and 'docker cp', but let's try strict echo for speed if code small
        # Or better: `docker exec -i CONTAINER sh -c 'cat > filename'`
        
        try:
            write_proc = await asyncio.create_subprocess_exec(
                "docker", "exec", "-i", self.container_id, "sh", "-c", f"cat > {filename}",
                stdin=asyncio.subprocess.PIPE
            )
            await write_proc.communicate(input=code.encode())
            
            # 2. Run file
            run_cmd = ["docker", "exec", self.container_id, "python", filename]
            run_proc = await asyncio.create_subprocess_exec(
                *run_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await run_proc.communicate()
            
            return {
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "exit_code": run_proc.returncode
            }
            
        except Exception as e:
            logger.error(f"Execution error: {e}")
            return {"error": str(e)}

    async def stop(self):
        """Stop and remove the container."""
        if self.container_id:
            subprocess.run(["docker", "stop", self.container_id], capture_output=True)
            self.container_id = None
            self.is_active = False
            logger.info("Sandbox stopped.")

# Example usage
# sandbox = DockerSandbox()
# await sandbox.start()
# res = await sandbox.execute_code("print('Hello from TARS Sandbox')")
# print(res)
# await sandbox.stop()
