from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["decisions"])


@router.get("/decisions")
def get_decisions():
    return {
        "decisions": []
    }