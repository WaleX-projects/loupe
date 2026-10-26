from fastapi import APIRouter
from .health import router as health_router
from .projects import router as projects_router
router_v1 = APIRouter(
    prefix='/v1',
    tags=["vi API Endpoints"]
)

router_v1.include_router(health_router)
router_v1.include_router(projects_router)



