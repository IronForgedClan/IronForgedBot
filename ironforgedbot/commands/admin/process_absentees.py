import io
import logging
import time
from datetime import datetime

import discord
from tabulate import tabulate

from ironforgedbot.common.helpers import format_duration
from ironforgedbot.common.text_formatters import text_h2
from ironforgedbot.database.database import db
from ironforgedbot.services.absent_service import AbsentMemberService

logger = logging.getLogger(__name__)


async def cmd_process_absentees(interaction: discord.Interaction):
    """Process and return absentee list."""
    await interaction.response.defer(thinking=True, ephemeral=False)
    start_time = time.perf_counter()

    async with db.get_session() as session:
        absent_service = AbsentMemberService(session)
        absentee_list = await absent_service.process_absent_members()

        data = []
        for member in absentee_list:
            data.append(
                [
                    member.nickname,
                    member.date,
                    member.information,
                    member.comment,
                ]
            )

        result_table = tabulate(
            data,
            headers=["Member", "Date", "Info", "Comment"],
            tablefmt="github",
        )
        discord_file = discord.File(
            fp=io.BytesIO(result_table.encode("utf-8")),
            filename=f"absentee_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        )
        end_time = time.perf_counter()

        return await interaction.followup.send(
            f"{text_h2('🚿 Absentee List')}\nThe following **{len(absentee_list)}**"
            " members will be ignored during an activity check. Processed in "
            f"**{format_duration(start_time, end_time)}**.",
            file=discord_file,
        )
