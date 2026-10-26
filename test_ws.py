# test_hitl.py
import asyncio
import json
import requests
import websockets

API_URL = "http://3.80.104.25:3000/v1/projects"
WS_BASE_URL = "ws://3.80.104.25:3000/ws/projects"
TOKEN = "secret-test-token"
PROMPT = "Clean up my resources"  # Trigger prompt that hits your ApprovalHook

def create_project():
    print("Creating project via API...")
    response = requests.post(API_URL, json={
        "name": "HITL Test Project",
        "description": "Testing human-in-the-loop breakpoints",
        "owner_id": "61c6614787db4212bdb1e014784a6a9b"
    })
    if response.status_code == 201:
        project_id = response.json().get("id")
        print(f"✅ Project created! ID: {project_id}")
        return project_id
    else:
        print(f"❌ Failed to create project: {response.text}")
        exit(1)

def trigger_job(project_id: str):
    print(f"Triggering initial job run for project {project_id}...")
    response = requests.post(f"{API_URL}/{project_id}/run", params={"prompt": PROMPT})
    if response.status_code in [200, 202]:
        print("✅ Job queued successfully!")
    else:
        print(f"❌ Failed to queue job: {response.text}")

def send_resume_response(project_id: str, user_input: str):
    print(f"▶️ Sending user response ('{user_input}') to resume workflow...")
    response = requests.post(f"{API_URL}/{project_id}/respond", params={"user_input": user_input})
    if response.status_code in [200, 202]:
        print("✅ Response queued for resumption!")
    else:
        print(f"❌ Failed to resume: {response.text}")

async def listen_and_test():
    project_id = create_project()
    trigger_job(project_id)
    
    uri = f"{WS_BASE_URL}/{project_id}?token={TOKEN}"
    print(f"Connecting to WebSocket: {uri}")
    
    async with websockets.connect(uri) as websocket:
        print("Connected! Listening for live events...\n")
        while True:
            raw_message = await websocket.recv()
            event = json.loads(raw_message)
            event_type = event.get("type")
            message = event.get("data", {}).get("message", "")
            
            print(f"📥 Event [{event_type}]: {message}")
            
            # When the swarm pauses for human approval, automatically reply 'yes'
            if event_type == "job_interrupted":
                print("\n⚠️ --- SWARM HIT BREAKPOINT (INTERRUPTED) ---")
                await asyncio.sleep(1) # Brief pause
                send_resume_response(project_id, "yes")
                print("-------------------------------------------\n")
                
            # Exit loop once the job successfully completes or fails
            elif event_type in ["job_completed", "job_failed"]:
                print(f"\n🏁 Test finished with status: {event_type}")
                break

if __name__ == "__main__":
    asyncio.run(listen_and_test())