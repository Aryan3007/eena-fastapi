from pydantic import BaseModel, Field


class UpdateProfileRequest(BaseModel):
    name: str | None = None
    bio: str | None = None
    avatar: str | None = None
    website: str | None = None


class CreateStoreRequest(BaseModel):
    store_name: str = Field(..., min_length=2, max_length=100)
    store_description: str | None = None
    store_logo: str | None = None
