import io
import logging

import discord
from tabulate import tabulate
from ironforgedbot.common.logging_utils import log_task_execution
from ironforgedbot.common.roles import ROLE, member_has_any_roles
from ironforgedbot.common.text_formatters import text_h2
from ironforgedbot.database.database import db
from ironforgedbot.services.ingot_service import IngotService
from ironforgedbot.services.service_factory import create_ingot_service
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

LEADERSHIP_PAYMENT = 50_000
STAFF_PAYMENT = 25_000
BOOSTER_PAYMENT = 10_000


def get_payment_month() -> str:
    first_of_this_month = datetime.now().replace(day=1)
    prev_month = first_of_this_month - timedelta(days=1)

    return prev_month.strftime("%B")


async def pay_group(
    service: IngotService, group: list[discord.Member], payment: int, reason: str
) -> str:
    output: list[list[str]] = []

    for member in group:
        try:
            payment_result = await service.try_add_ingots(
                member.id, payment, None, reason
            )
        except Exception as e:
            logger.error(f"Failed to pay {member.display_name}: {e}")
            continue

        if not payment_result:
            output.append(
                [
                    member.display_name,
                    "0",
                    "?",
                ]
            )

            logger.error(
                f"Payment response invalid for {member.display_name}: {payment_result}"
            )
            continue

        if not payment_result.status:
            output.append(
                [
                    member.display_name,
                    "0",
                    f"{payment_result.new_total:,}",
                ]
            )
            logger.info(
                f"Payment failed for {member.display_name}: {payment_result.message}"
            )
            continue

        logger.debug(f"Paid {member.display_name} {payment} ingots: {reason}")
        output.append(
            [
                member.display_name,
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
    guild: discord.Guild,
    report_channel: discord.TextChannel,
):
    """Runs the ingot payroll for Leadership, Staff and Boosters

    Args:
        guild: Discord Guild
        report_channel: The channel to send output reports
    """
    month_name = get_payment_month()

    leadership_members: list[discord.Member] = []
    staff_members: list[discord.Member] = []
    booster_members: list[discord.Member] = []

    for member in guild.members:
        if member_has_any_roles(member, [ROLE.LEADERSHIP]):
            leadership_members.append(member)
        elif member_has_any_roles(member, [ROLE.STAFF]):
            # NOTE: elif so as to not include Leadership members in Staff list
            staff_members.append(member)

        if member_has_any_roles(member, [ROLE.BOOSTER]):
            booster_members.append(member)

    async with db.get_session() as session:
        service = create_ingot_service(session)

        leadership_output = await pay_group(
            service,
            leadership_members,
            LEADERSHIP_PAYMENT,
            f"{month_name} leadership payment",
        )
        staff_output = await pay_group(
            service, staff_members, STAFF_PAYMENT, f"{month_name} staff payment"
        )
        booster_output = await pay_group(
            service, booster_members, BOOSTER_PAYMENT, f"{month_name} booster payment"
        )

    for output, group_name in [
        (leadership_output, "Leadership"),
        (staff_output, "Staff"),
        (booster_output, "Nitro Boosters"),
    ]:
        await report_payroll(report_channel, output, group_name, month_name)
