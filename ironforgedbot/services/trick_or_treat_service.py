from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ironforgedcore.models.changelog import ChangeType, Changelog
from ironforgedcore.models.member import Member


@dataclass
class TrickOrTreatTransferResponse:
    status: bool
    message: str
    amount: int
    source_total: int
    target_total: int


class TrickOrTreatService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def transfer_ingots(
        self,
        source_discord_id: int,
        target_discord_id: int,
        amount: int,
        reason: str,
    ) -> TrickOrTreatTransferResponse:
        if amount < 1 or source_discord_id == target_discord_id:
            return TrickOrTreatTransferResponse(False, "Invalid transfer", 0, 0, 0)

        async with self.session.begin():
            result = await self.session.execute(
                select(Member)
                .where(Member.discord_id.in_([source_discord_id, target_discord_id]))
                .order_by(Member.discord_id)
                .with_for_update()
            )
            members = {member.discord_id: member for member in result.scalars().all()}
            source = members.get(source_discord_id)
            target = members.get(target_discord_id)

            if source is None or target is None:
                return TrickOrTreatTransferResponse(
                    False, "Member could not be found", 0, 0, 0
                )

            if source.ingots < amount:
                return TrickOrTreatTransferResponse(
                    False, "Insufficient balance", 0, 0, 0
                )

            now = datetime.now(timezone.utc)
            source_total = source.ingots - amount
            target_total = target.ingots + amount
            self.session.add_all(
                [
                    Changelog(
                        member_id=source.id,
                        admin_id=None,
                        change_type=ChangeType.REMOVE_INGOTS,
                        previous_value=source.ingots,
                        new_value=source_total,
                        comment=reason,
                        timestamp=now,
                    ),
                    Changelog(
                        member_id=target.id,
                        admin_id=None,
                        change_type=ChangeType.ADD_INGOTS,
                        previous_value=target.ingots,
                        new_value=target_total,
                        comment=reason,
                        timestamp=now,
                    ),
                ]
            )
            source.ingots = source_total
            target.ingots = target_total
            source.last_changed_date = now
            target.last_changed_date = now

            return TrickOrTreatTransferResponse(
                True,
                "Transfer completed",
                amount,
                source_total,
                target_total,
            )
