from pydantic import BaseModel
from uuid import UUID

class AllowedViewerAddIn(BaseModel):
    viewer_id: UUID
