import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.errors import Forbidden, HTTPException
from discord.ui import Modal, TextInput, View

from ironforgedbot.common.helpers import datetime_to_discord_relative
from ironforgedbot.common.logging_utils import log_method_execution
from ironforgedbot.common.responses import build_response_embed, send_ephemeral_error
from ironforgedcore.database import db
from ironforgedbot.services.service_factory import create_member_service

logger = logging.getLogger(__name__)

VIEW_TIMEOUT_SECONDS = 300


class SetJoinDateView(View):
    def __init__(
        self,
        *,
        report_channel: discord.TextChannel,
        guild: discord.Guild,
        message: Optional[discord.Message] = None,
    ):
        super().__init__(timeout=VIEW_TIMEOUT_SECONDS)
        self.report_channel = report_channel
        self.guild = guild
        self.message = message
        self.target_member: Optional[discord.Member] = None
        self.target_joined_date: Optional[datetime] = None
        self._sync_button_state()

    async def on_timeout(self) -> None:
        await self._delete_message()
        return await super().on_timeout()

    async def _delete_message(self) -> None:
        if self.message:
            try:
                await self.message.delete()
            except Forbidden, HTTPException:
                pass

    def _sync_button_state(self) -> None:
        can_continue = (
            self.target_member is not None and self.target_joined_date is not None
        )
        for child in self.children:
            if (
                isinstance(child, discord.ui.Button)
                and child.custom_id == "set_join_date_continue"
            ):
                child.disabled = not can_continue

    def _build_embed(self) -> discord.Embed:
        description = (
            "Select the member whose join date should be manually updated.\n\n"
            "On the next screen, enter the new join date as `YYYY-MM-DD` (UTC)."
        )
        if self.target_member:
            description += (
                f"\n---\n**Selected:** {self.target_member.mention} "
                f"(`{self.target_member.id}`)"
            )
            if self.target_joined_date is not None:
                short = datetime_to_discord_relative(self.target_joined_date, "d")
                relative = datetime_to_discord_relative(self.target_joined_date, "R")
                description += f"\n**Current join date:** {short} ({relative})"

        return build_response_embed(
            ":calendar: Set Join Date",
            description,
            discord.Colour.blue(),
        )

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="Select a member...",
        min_values=1,
        max_values=1,
        row=0,
    )
    async def member_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.UserSelect,
    ):
        selected = select.values[0]

        db_member = None
        async with db.get_session() as session:
            service = create_member_service(session)
            db_member = await service.get_member_by_discord_id(selected.id)

        if db_member is None or not db_member.active:
            self.target_member = None
            self.target_joined_date = None
            self._sync_button_state()
            return await interaction.response.edit_message(
                embed=_build_blocked_embed(selected), view=self
            )

        self.target_member = selected
        joined = db_member.joined_date
        if joined is not None and joined.tzinfo is None:
            joined = joined.replace(tzinfo=timezone.utc)
        self.target_joined_date = joined
        self._sync_button_state()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @discord.ui.button(
        label="Continue",
        style=discord.ButtonStyle.green,
        custom_id="set_join_date_continue",
        row=1,
    )
    async def continue_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not self.target_member or self.target_joined_date is None:
            return

        await interaction.response.send_modal(
            SetJoinDateModal(
                target_user=self.target_member,
                original_date=self.target_joined_date,
                report_channel=self.report_channel,
                admin_discord_id=interaction.user.id,
            )
        )

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.grey,
        custom_id="set_join_date_cancel",
        row=1,
    )
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self._delete_message()
        if not interaction.response.is_done():
            await interaction.response.send_message("Cancelled.", ephemeral=True)


def _build_blocked_embed(blocked_user: discord.Member) -> discord.Embed:
    description = (
        f":warning: **{blocked_user.mention}** is not registered in the database, "
        "or is not an active member. Pick another member to set their join date."
    )
    return build_response_embed(
        ":calendar: Set Join Date",
        description,
        discord.Colour.red(),
    )


class SetJoinDateModal(Modal):
    def __init__(
        self,
        *,
        target_user: discord.Member,
        original_date: datetime,
        report_channel: discord.TextChannel,
        admin_discord_id: Optional[int] = None,
    ):
        super().__init__(title="Set Join Date")

        self.target_user = target_user
        self.original_date = original_date
        self.report_channel = report_channel
        self.admin_discord_id = admin_discord_id

        self.date_input = TextInput(
            label="Join date (YYYY-MM-DD, UTC)",
            placeholder=original_date.strftime("%Y-%m-%d"),
            required=True,
            max_length=10,
            style=discord.TextStyle.short,
        )
        self.add_item(self.date_input)

    async def on_submit(self, interaction: discord.Interaction):
        raw_value = (self.date_input.value or "").strip()

        try:
            parsed = datetime.strptime(raw_value, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            return await send_ephemeral_error(
                interaction,
                f"`{raw_value}` is not a valid date. Use `YYYY-MM-DD`.",
            )

        today_utc = datetime.now(tz=timezone.utc).date()
        if parsed.date() > today_utc:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            return await send_ephemeral_error(
                interaction, "Join date cannot be in the future."
            )

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        error_embed = await _execute_set(
            target_user=self.target_user,
            new_date=parsed,
            report_channel=self.report_channel,
            admin_discord_id=self.admin_discord_id,
        )

        if error_embed is not None:
            await send_ephemeral_error(
                interaction, error_embed.description or "Update failed."
            )
            return

        try:
            await interaction.followup.send(
                ":white_check_mark: Join date updated.", ephemeral=True
            )
        except (Forbidden, HTTPException) as e:
            logger.error(f"Failed to send set-join-date ephemeral ack: {e}")


async def _resolve_admin_db_id(discord_id: Optional[int]) -> Optional[str]:
    if discord_id is None:
        return None
    try:
        async with db.get_session() as session:
            service = create_member_service(session)
            admin = await service.get_member_by_discord_id(discord_id)
            if admin:
                return admin.id
    except Exception as e:
        logger.error(f"Could not resolve admin DB id: {e}")
    return None


async def _post_report(report_channel: discord.TextChannel, text: str) -> None:
    try:
        await report_channel.send(text)
    except (Forbidden, HTTPException) as e:
        logger.error(f"Failed to post set-join-date report: {e}")


async def _execute_set(
    *,
    target_user: discord.Member,
    new_date: datetime,
    report_channel: discord.TextChannel,
    admin_discord_id: Optional[int] = None,
) -> Optional[discord.Embed]:
    """Apply the join date change. Returns an error embed on failure, None on success."""
    admin_mention = f"<@{admin_discord_id}>" if admin_discord_id else "<@unknown>"

    try:
        async with db.get_session() as session:
            service = create_member_service(session)
            db_member = await service.get_member_by_discord_id(target_user.id)

            if db_member is None:
                await _post_report(
                    report_channel,
                    f":warning: Failed to set join date for {target_user.mention}: "
                    "not registered in the database.",
                )
                return build_response_embed(
                    ":x: Member not registered",
                    f"{target_user.mention} (`{target_user.id}`) is not linked "
                    "to a member in the database.",
                    discord.Colour.red(),
                )

            previous_joined_date = db_member.joined_date

        admin_db_id = await _resolve_admin_db_id(admin_discord_id)

        try:
            async with db.get_session() as session:
                service = create_member_service(session)
                await service.change_joined_date(
                    id=db_member.id,
                    new_joined_date=new_date,
                    admin_id=admin_db_id,
                    comment="Manually set join date",
                )
        except Exception as e:
            logger.critical(f"Unexpected DB error during set-join-date: {e}")
            await _post_report(
                report_channel,
                (
                    f":warning: Failed to set join date for {target_user.mention}: "
                    f"db update failed: `{e}`."
                ),
            )
            return build_response_embed(
                ":x: DB update failed",
                f"Could not update join date in the database: `{e}`.",
                discord.Colour.red(),
            )

        prev_display = (
            datetime_to_discord_relative(previous_joined_date, "d")
            if isinstance(previous_joined_date, datetime)
            else str(previous_joined_date)
        )
        new_display = datetime_to_discord_relative(new_date, "d")

        await _post_report(
            report_channel,
            (
                f":calendar: {admin_mention} set join date for "
                f"{target_user.mention} (`{target_user.id}`): "
                f"{prev_display} → {new_display}"
            ),
        )
        return None
    except Exception as e:
        logger.critical(f"Unhandled exception in set join date: {e}")
        await _post_report(
            report_channel,
            (
                f":warning: Failed to set join date for {target_user.mention}: "
                f"unexpected error: `{e}`."
            ),
        )
        return build_response_embed(
            ":x: Unexpected error",
            f"An unexpected error occurred: `{e}`.",
            discord.Colour.red(),
        )


@log_method_execution(logger)
async def cmd_set_join_date(
    interaction: discord.Interaction, report_channel: discord.TextChannel
) -> None:
    """Entry point invoked by the admin menu button."""
    if not interaction.guild:
        return

    await interaction.response.defer(ephemeral=True)

    view = SetJoinDateView(
        report_channel=report_channel,
        guild=interaction.guild,
    )
    embed = view._build_embed()
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    try:
        view.message = await interaction.original_response()
    except Exception:
        pass
