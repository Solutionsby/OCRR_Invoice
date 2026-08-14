from fastapi import APIRouter, HTTPException

from core import paths
from api.schemas import FolderConfig, FolderRole, BrowseResult

router = APIRouter(prefix="/api/folders", tags=["folders"])


@router.get("", response_model=list[FolderRole])
def get_folders():
    return paths.get_folders_resolved()


@router.put("", response_model=list[FolderRole])
def put_folders(body: FolderConfig):
    try:
        paths.save_folders(body.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return paths.get_folders_resolved()


@router.get("/browse", response_model=BrowseResult)
def browse(path: str = ""):
    """
    Lista podfolderów BASE_PATH/path — do klikalnej przeglądarki folderów w
    UI. `path` puste = korzeń zamontowanego katalogu.
    """
    try:
        subfolders = paths.list_subfolders(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    parent = None
    if path:
        parts = path.strip("/").split("/")
        parent = "/".join(parts[:-1])

    return {"path": path, "parent": parent, "subfolders": subfolders}
