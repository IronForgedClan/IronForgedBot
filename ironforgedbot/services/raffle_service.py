import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import Sequence, delete, func, select, update, values
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import session

from ironforgedbot.models.changelog import Changelog, ChangeType
from ironforgedbot.models.member import Member
from ironforgedbot.models.raffle_ticket import RaffleTicket
from ironforgedbot.services.ingot_service import IngotService
from ironforgedbot.services.member_service import MemberService

logger = logging.getLogger(__name__)


class RaffleServiceException(Exception):
    def __init__(self, message="An error occured interacting with the raffle"):
        self.message = message
        super().__init__(self.message)


@dataclass
class RaffleServiceResponse:
    status: bool
    message: str
    ticket_total: int


class RaffleService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.member_service = MemberService(db)
        self.ingot_service = IngotService(db)

    async def close(self):
        await self.ingot_service.close()
        await self.db.close()

    async def get_member_ticket_total(self, discord_id: int) -> int:
        result = await self.db.execute(
            select(RaffleTicket)
            .join(Member, RaffleTicket.member_id == Member.id)
            .where(Member.discord_id == discord_id)
        )
        data: Optional[RaffleTicket] = result.scalars().first()

        if not data:
            return 0

        return data.quantity

    async def get_raffle_ticket_total(self) -> int:
        result = await self.db.execute(select(func.sum(RaffleTicket.quantity)))
        total = result.scalars().first()
        return total if total is not None else 0

    async def get_all_valid_raffle_tickets(self) -> list[RaffleTicket]:
        result = await self.db.execute(
            select(RaffleTicket).join(Member).where(Member.active.is_(True))
        )
        return list(result.scalars().all())

    async def _get_raffle_ticket(self, id: str) -> RaffleTicket | None:
        result = await self.db.execute(
            select(RaffleTicket).where(RaffleTicket.member_id == id)
        )
        return result.scalars().first()

    async def delete_all_tickets(self):
        await self.db.execute((delete(RaffleTicket)))
        await self.db.commit()

    async def try_buy_ticket(
        self, discord_id: int, ticket_price: int, quantity: int
    ) -> RaffleServiceResponse:
        now = datetime.now(timezone.utc)

        if quantity < 1:
            return RaffleServiceResponse(
                False, "Quantity must be a positive integer", -1
            )

        if ticket_price < 1:
            return RaffleServiceResponse(
                False, "Ticket price must be a positive integer", -1
            )

        member = await self.member_service.get_member_by_discord_id(discord_id)
        if not member:
            return RaffleServiceResponse(False, "Member could not be found", -1)

        logger.info(
            f"Attempting to buy {quantity} raffle tickets for {member.nickname}"
        )

        current_raffle_ticket = await self._get_raffle_ticket(member.id)

        total_cost = ticket_price * quantity
        ingot_response = await self.ingot_service.try_remove_ingots(
            discord_id, -total_cost, None, "Purchase raffle tickets"
        )

        if ingot_response.status is False:
            return RaffleServiceResponse(
                False, ingot_response.message, current_raffle_ticket or 0
            )

        if current_raffle_ticket:
            new_ticket_quantity = current_raffle_ticket.quantity + quantity
            self.db.add(
                Changelog(
                    member_id=member.id,
                    admin_id=None,
                    change_type=ChangeType.PURCHASE_RAFFLE_TICKETS,
                    previous_value=current_raffle_ticket.quantity,
                    new_value=new_ticket_quantity,
                    comment="Purchased raffle tickets",
                    timestamp=now,
                )
            )

            await self.db.execute(
                update(RaffleTicket)
                .where(RaffleTicket.member_id == member.id)
                .values(quantity=new_ticket_quantity, last_changed_date=now)
            )

            await self.db.commit()

            return RaffleServiceResponse(
                True, f"{quantity} raffle tickets purchased", new_ticket_quantity
            )
        else:
            self.db.add(
                Changelog(
                    member_id=member.id,
                    admin_id=None,
                    change_type=ChangeType.PURCHASE_RAFFLE_TICKETS,
                    previous_value=0,
                    new_value=quantity,
                    comment="Purchased raffle tickets",
                    timestamp=now,
                )
            )

            self.db.add(
                RaffleTicket(
                    member_id=member.id, quantity=quantity, last_changed_date=now
                )
            )

            await self.db.commit()

            return RaffleServiceResponse(
                True, f"{quantity} raffle tickets purchased", quantity
            )
