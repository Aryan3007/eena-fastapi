from pydantic import BaseModel, Field


class CreateCampaignRequest(BaseModel):
    campaign_title: str = Field(..., min_length=2, max_length=200)
    product: str  # Product ID
    commission_percentage: float = Field(..., ge=0, le=100)


class InviteInfluencerRequest(BaseModel):
    influencer_id: str


class RespondCollaborationRequest(BaseModel):
    status: str  # ACCEPTED | REJECTED
