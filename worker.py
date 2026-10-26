import asyncio
import json
import logging
from app.services.redis_client import redis_client
from app.worker.runner import TaskRunner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LoupeWorker")

async def main():
    logger.info("🚀 Loupe Worker started and listening for jobs...")
    
    while True:
        try:
            # Block and wait until a job appears in the Redis queue (timeout after 5 seconds)
            result = await redis_client.blpop("loupe_job_queue", timeout=5)
            
            if result:
                queue_name, raw_data = result
                job = json.loads(raw_data)
                project_id = job.get("project_id")
                action = job.get("action")
                
                try:
                    # Check if this is a human-in-the-loop continuation
                    if action == "resume":
                        user_input = job.get("user_input")
                        logger.info(f"🔄 Resuming job for project {project_id} with input: {user_input}")
                        
                        await TaskRunner.resume_job(project_id, user_input)
                        
                        logger.info(f"✅ Successfully completed resumed workflow for project: {project_id}")
                    else:
                        # Standard fresh start
                        prompt = job.get("prompt")
                        logger.info(f"📥 Received new job for project: {project_id}")
                        
                        await TaskRunner.run_job(project_id, prompt)
                        
                        logger.info(f"✅ Successfully completed job for project: {project_id}")
                        
                except Exception as e:
                    logger.error(f"❌ Failed job for project {project_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Worker loop error: {e}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())