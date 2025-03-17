import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedbot.models.changelog import Changelog, ChangeType
from ironforgedbot.services.member_service import MemberService

logger = logging.getLogger(__name__)


@dataclass
class IngotServiceResponse:
    status: bool
    message: str
    new_total: int


class IngotService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.member_service = MemberService(db)

    async def close(self):
        await self.member_service.close()
        await self.db.close()

    async def try_add_ingots(
        self, discord_id: int, quantity: int, admin_discord_id: int, reason: str
    ) -> IngotServiceResponse:
        now = datetime.now(timezone.utc)

        if quantity < 1:
            return IngotServiceResponse(False, "Quantity must be a positive value", -1)

        member = await self.member_service.get_member_by_discord_id(discord_id)
        if not member:
            return IngotServiceResponse(False, "Member could not be found", -1)

        admin_member = await self.member_service.get_member_by_discord_id(
            admin_discord_id
        )
        if not admin_member:
            return IngotServiceResponse(False, "Admin member could not be found", -1)

        logger.info(
            f"Attempting to add {quantity} ingots to {member.nickname} on behalf of {admin_member.nickname}"
        )

        new_ingot_total = member.ingots + quantity

        self.db.add(
            Changelog(
                member_id=member.id,
                admin_id=admin_member.id,
                change_type=ChangeType.ADD_INGOTS,
                previous_value=member.ingots,
                new_value=new_ingot_total,
                comment=reason or "Adding ingots",
                timestamp=now,
            )
        )

        member.ingots = new_ingot_total
        member.last_changed_date = now

        await self.db.commit()
        await self.db.refresh(member)

        return IngotServiceResponse(True, "Ingots added", new_ingot_total)

    async def try_remove_ingots(
        self, discord_id: int, quantity: int, admin_discord_id: int, reason: str
    ) -> IngotServiceResponse:
        now = datetime.now(timezone.utc)

        if quantity > -1:
            return IngotServiceResponse(
                False, "Quantity to remove must be a negative value", -1
            )

        member = await self.member_service.get_member_by_discord_id(discord_id)
        if not member:
            return IngotServiceResponse(False, "Member could not be found", -1)

        admin_member = await self.member_service.get_member_by_discord_id(
            admin_discord_id
        )
        if not admin_member:
            return IngotServiceResponse(False, "Admin member could not be found", -1)

        logger.info(
            f"Attempting to remove {quantity} ingots from {member.nickname} on behalf of {admin_member.nickname}"
        )

        new_ingot_total = member.ingots + quantity
        new_ingot_total = member.ingots + quantity

        if new_ingot_total < 0:
            return IngotServiceResponse(
                False,
                "Member does not have enough ingots to remove that amount",
                member.ingots,
            )

        self.db.add(
            Changelog(
                member_id=member.id,
                admin_id=admin_member.id,
                change_type=ChangeType.REMOVE_INGOTS,
                previous_value=member.ingots,
                new_value=new_ingot_total,
                comment=reason or "Removing ingots",
                timestamp=now,
            )
        )

        member.ingots = new_ingot_total
        member.last_changed_date = now

        await self.db.commit()
        await self.db.refresh(member)

        return IngotServiceResponse(True, "Ingots removed", new_ingot_total)
