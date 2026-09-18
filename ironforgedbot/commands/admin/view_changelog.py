import io
import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ui import View

from ironforgedbot.common.responses import send_error_response
from ironforgedbot.common.text_formatters import text_ascii_table
from ironforgedbot.services.service_factory import (
    create_changelog_service,
    create_member_service,
)
from ironforgedcore.common.changelog_labels import label_for_change_type
from ironforgedcore.database import db
from ironforgedcore.models.changelog import Changelog

logger = logging.getLogger(__name__)

VIEW_TIMEOUT_SECONDS = 120

_TABLE_HEADERS = ("Timestamp", "Type", "Previous", "New", "Comment", "Admin")
_TABLE_WRAP_WIDTHS = (19, 20, 22, 22, 26, 16)


def _format_timestamp(timestamp: datetime) -> str:
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _admin_label(entry: Changelog) -> str:
    admin_member = getattr(entry, "admin_member", None)
    if admin_member is not None:
        nickname = getattr(admin_member, "nickname", None)
        if nickname:
            return nickname
    return "System"


def _build_changelog_rows(entries: list[Changelog]) -> list[tuple]:
    rows = []
    for entry in entries:
        rows.append(
            (
                _format_timestamp(entry.timestamp),
                label_for_change_type(entry.change_type),
                entry.previous_value or "-",
                entry.new_value or "-",
                entry.comment or "-",
                _admin_label(entry),
            )
        )
    return rows


def _build_changelog_text_body(
    entries: list[Changelog], nickname: str, *, window_label: str | None = None
) -> str:
    rows = _build_changelog_rows(entries)
    suffix = f" ({window_label})" if window_label else ""
    header_line = f"# Changelog for {nickname}{suffix}\n"
    if not rows:
        table = text_ascii_table(
            [],
            headers=_TABLE_HEADERS,
            wrap_widths=_TABLE_WRAP_WIDTHS,
            colalign=("left", "left", "left", "left", "left", "left"),
            code_block=False,
        )
        return f"{header_line}\nNo changelog entries found.\n\n{table}\n"

    table = text_ascii_table(
        rows,
        headers=_TABLE_HEADERS,
        wrap_widths=_TABLE_WRAP_WIDTHS,
        colalign=("left", "left", "left", "left", "left", "left"),
        code_block=False,
    )
    return f"{header_line}\n{table}\n"


def _build_report_message(admin_mention: str, db_member) -> str:
    return (
        f":scroll: {admin_mention} viewed changelog for "
        f"**{db_member.nickname}** (<@{db_member.discord_id}>)."
    )


async def cmd_view_changelog(
    interaction: discord.Interaction, report_channel: discord.TextChannel
) -> None:
    await interaction.response.defer(thinking=True, ephemeral=True)

    view = ChangelogSelectView(report_channel=report_channel)
    message = await interaction.followup.send(
        content="## :scroll: View Member Changelog",
        view=view,
        ephemeral=True,
    )
    view.message = message


class ChangelogSelectView(View):
    def __init__(
        self,
        *,
        report_channel: discord.TextChannel,
        timeout: float = VIEW_TIMEOUT_SECONDS,
    ):
        super().__init__(timeout=timeout)
        self.report_channel = report_channel
        self.message: Optional[discord.Message] = None

    async def on_timeout(self) -> None:
        if self.message is not None:
            try:
                await self.message.delete()
            except discord.Forbidden, discord.HTTPException:
                pass
        return await super().on_timeout()

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="Select a member to view changelog for...",
        min_values=1,
        max_values=1,
    )
    async def member_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.UserSelect,
    ):
        await interaction.response.defer(thinking=True, ephemeral=True)

        target_member = select.values[0]
        discord_id = target_member.id
        admin_mention = interaction.user.mention

        async with db.get_session() as session:
            member_service = create_member_service(session)
            changelog_service = create_changelog_service(session)

            db_member = await member_service.get_member_by_discord_id(discord_id)
            if db_member is None:
                return await send_error_response(
                    interaction,
                    f":warning: <@{discord_id}> is not registered in the database.",
                )
            if not db_member.active:
                return await send_error_response(
                    interaction,
                    f":warning: **{db_member.nickname}** is not an active member.",
                )

            entries = await changelog_service.get_changelog_for_member(
                discord_id, days=30
            )

        body = _build_changelog_text_body(
            entries, db_member.nickname, window_label="last 30 days"
        )
        safe_nick = (
            "".join(
                ch for ch in db_member.nickname if ch.isalnum() or ch in ("-", "_")
            ).lower()
            or "member"
        )
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"changelog_{safe_nick}_{timestamp}.txt"
        discord_file = discord.File(io.BytesIO(body.encode("utf-8")), filename=filename)

        if self.message is not None:
            try:
                await self.message.delete()
            except discord.Forbidden, discord.HTTPException:
                pass

        await interaction.followup.send(file=discord_file, ephemeral=True)

        try:
            await self.report_channel.send(
                _build_report_message(admin_mention, db_member)
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            logger.error(f"Failed to post changelog report to channel: {e}")
