from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter(tags=["系統"])


@router.get("/")
def home():
    return RedirectResponse(url="/view/home")
