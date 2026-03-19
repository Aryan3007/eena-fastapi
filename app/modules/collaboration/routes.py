import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.middleware.auth import get_current_user, require_roles
from app.config.database import get_db
from app.modules.collaboration.models import Collaboration
from app.modules.collaboration.schemas import (
    CreateCampaignRequest,
    InviteInfluencerRequest,
    RespondCollaborationRequest,
)
from app.modules.user.models import User

router = APIRouter(prefix="/collaborations", tags=["Collaborations"])


def _serialize_collab(c: Collaboration) -> dict:
    return {
        "_id": str(c.id),
        "brand": str(c.brand_id),
        "influencer": str(c.influencer_id),
        "campaignTitle": c.campaign_title,
        "product": str(c.product_id),
        "commissionPercentage": c.commission_percentage,
        "status": c.status,
        "reel": str(c.reel_id) if c.reel_id else None,
        "createdAt": c.created_at.isoformat() if c.created_at else None,
    }


@router.post("/campaigns", status_code=status.HTTP_201_CREATED)
async def create_campaign(
    body: CreateCampaignRequest,
    user: User = Depends(require_roles("BRAND")),
) -> dict:
    return {
        "campaign": {
            "brand": str(user.id),
            "campaignTitle": body.campaign_title,
            "product": body.product,
            "commissionPercentage": body.commission_percentage,
        }
    }


@router.get("/campaigns")
async def list_campaigns(
    user: User = Depends(require_roles("BRAND")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Collaboration)
        .where(Collaboration.brand_id == user.id)
        .order_by(Collaboration.created_at.desc())
    )
    collabs = result.scalars().all()
    return {"campaigns": [_serialize_collab(c) for c in collabs]}


@router.post("/campaigns/{campaign_id}/invite", status_code=status.HTTP_201_CREATED)
async def invite_influencer(
    campaign_id: str,
    body: InviteInfluencerRequest,
    user: User = Depends(require_roles("BRAND")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    influencer_id = uuid.UUID(body.influencer_id)
    result = await db.execute(select(User).where(User.id == influencer_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Influencer not found")

    collab = Collaboration(
        brand_id=user.id,
        influencer_id=influencer_id,
        campaign_title=f"Campaign {campaign_id}",
        product_id=uuid.UUID(campaign_id),
        commission_percentage=10.0,
    )
    db.add(collab)
    await db.flush()
    return {"collaboration": _serialize_collab(collab)}


@router.get("/brand")
async def brand_collaborations(
    user: User = Depends(require_roles("BRAND")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Collaboration)
        .where(Collaboration.brand_id == user.id)
        .order_by(Collaboration.created_at.desc())
    )
    collabs = result.scalars().all()
    return {"collaborations": [_serialize_collab(c) for c in collabs]}


@router.get("/invites")
async def influencer_invites(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Collaboration)
        .where(Collaboration.influencer_id == user.id, Collaboration.status == "PENDING")
        .order_by(Collaboration.created_at.desc())
    )
    collabs = result.scalars().all()
    return {"invites": [_serialize_collab(c) for c in collabs]}


@router.patch("/{collab_id}/respond")
async def respond_to_invite(
    collab_id: uuid.UUID,
    body: RespondCollaborationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if body.status not in ("ACCEPTED", "REJECTED"):
        raise HTTPException(status_code=400, detail="Invalid status")

    result = await db.execute(select(Collaboration).where(Collaboration.id == collab_id))
    collab = result.scalar_one_or_none()
    if not collab:
        raise HTTPException(status_code=404, detail="Collaboration not found")
    if collab.influencer_id != user.id:
        raise HTTPException(status_code=403, detail="Not your invite")
    if collab.status != "PENDING":
        raise HTTPException(status_code=400, detail="Already responded")

    collab.status = body.status
    await db.flush()
    return {"collaboration": _serialize_collab(collab)}
