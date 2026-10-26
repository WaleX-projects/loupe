from fastapi import APIRouter

# Initialize the router with a root prefix and documentation tags
router = APIRouter(
    
    tags=["Health and Account"]
)

# Liveness check endpoint to verify the application is running
@router.get("/healthz")
def health():
    return {'status': True}

# Readiness check endpoint to verify the application is ready to accept traffic
@router.get("/readyz")
def readiness():
    return {'status': True}