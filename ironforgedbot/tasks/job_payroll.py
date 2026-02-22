import io
import logging
from datetime import datetime, timedelta

import discord
from tabulate import tabulate

from ironforgedbot.common.logging_utils import log_task_execution
from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.text_formatters import text_h2
from ironforgedbot.database.database import db
from ironforgedbot.models.member import Member
from ironforgedbot.services.ingot_service import IngotService
from ironforgedbot.services.service_factory import (
    create_ingot_service,
    create_member_service,
)

logger = logging.getLogger(__name__)

LEADERSHIP_PAYMENT = 50_000
STAFF_PAYMENT = 25_000
BOOSTER_PAYMENT = 10_000


def get_payment_month() -> str:
    first_of_this_month = datetime.now().replace(day=1)
    prev_month = first_of_this_month - timedelta(days=1)

    return prev_month.strftime("%B")


async def pay_group(
    service: IngotService, group: list[Member], payment: int, reason: str
) -> str:
    output: list[list[str]] = []

    for member in group:
        try:
            payment_result = await service.try_add_ingots(
                member.discord_id, payment, None, reason
            )
        except Exception as e:
            logger.error(f"Failed to pay {member.nickname}: {e}")
            continue

        if not payment_result:
            output.append(
                [
                    member.nickname,
                    "0",
                    "?",
                ]
            )

            logger.error(
                f"Payment response invalid for {member.nickname}: {payment_result}"
            )
            continue

        if not payment_result.status:
            output.append(
                [
                    member.nickname,
                    "0",
                    f"{payment_result.new_total:,}",
                ]
            )
            logger.info(
                f"Payment failed for {member.nickname}: {payment_result.message}"
            )
            continue

        logger.debug(f"Paid {member.nickname} {payment} ingots: {reason}")
        output.append(
            [
                member.nickname,
                f"+{payment:,}",
                f"{payment_result.new_total:,}",
            ]
        )

    return tabulate(output, headers=["Member", "Change", "Total"], tablefmt="github")


async def report_payroll(
    channel: discord.TextChannel, table: str, group_name: str, month: str
) -> None:
    discord_file = discord.File(
        fp=io.BytesIO(table.encode("utf-8")),
        filename=f"payroll_{group_name.replace(" ", "_").lower()}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt",
    )

    await channel.send(
        (
            f"{text_h2(f"💰 {month} {group_name} Payroll")}\n"
            "Automated payroll has been processed for the following members:"
        ),
        file=discord_file,
    )


@log_task_execution(logger)
async def job_payroll(
    report_channel: discord.TextChannel,
):
    """Runs the ingot payroll for Leadership, Staff and Boosters

    Args:
        report_channel: The channel to send output reports
    """
    month_name = get_payment_month()

    async with db.get_session() as session:
        member_service = create_member_service(session)
        ingot_service = create_ingot_service(session)

        leadership_roles = ROLE.ADMIRAL.or_higher()
        db_leadership = await member_service.get_active_members_by_roles(
            [ROLE(r) for r in leadership_roles]
        )

        staff_roles = [ROLE.STAFF, ROLE.BRIGADIER]
        db_staff = await member_service.get_active_members_by_roles(staff_roles)
        db_boosters = await member_service.get_active_boosters()

        # Exclude leadership members from staff to prevent double payment
        leadership_ids = {m.discord_id for m in db_leadership}
        staff_members = [m for m in db_staff if m.discord_id not in leadership_ids]

        leadership_output = await pay_group(
            ingot_service,
            db_leadership,
            LEADERSHIP_PAYMENT,
            f"{month_name} leadership payment",
        )
        staff_output = await pay_group(
            ingot_service, staff_members, STAFF_PAYMENT, f"{month_name} staff payment"
        )
        booster_output = await pay_group(
            ingot_service,
            db_boosters,
            BOOSTER_PAYMENT,
            f"{month_name} booster payment",
        )

    for output, group_name in [
        (leadership_output, "Leadership"),
        (staff_output, "Staff"),
        (booster_output, "Nitro Boosters"),
    ]:
        await report_payroll(report_channel, output, group_name, month_name)
