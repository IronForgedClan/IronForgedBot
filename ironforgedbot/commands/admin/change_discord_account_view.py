import logging
from dataclasses import dataclass, field
from typing import Optional

import discord
from discord.errors import Forbidden, HTTPException
from discord.ui import View
from sqlalchemy.exc import IntegrityError

from ironforgedbot.common.constants import EMPTY_SPACE
from ironforgedbot.common.discord_retry import discord_write_with_retry
from ironforgedbot.common.logging_utils import log_method_execution
from ironforgedbot.common.responses import build_response_embed
from ironforgedbot.events import member_update_emitter
from ironforgedcore.common.ranks import GOD_ALIGNMENT, RANK
from ironforgedcore.common.role_names import (
    BANNED_ROLE_NAME,
    BLACKLISTED_ROLE_NAME,
    PROSPECT_ROLE_NAME,
)
from ironforgedcore.common.roles import ROLE
from ironforgedcore.database import db
from ironforgedcore.services.member_service import UniqueDiscordIdVolation
from ironforgedbot.services.service_factory import create_member_service

logger = logging.getLogger(__name__)

SUPPRESS_DURATION_MS = 5000
CHANGELOG_COMMENT_MAX_LENGTH = 255
VIEW_TIMEOUT_SECONDS = 300


def _get_tracked_role_names() -> set[str]:
    return (
        set(RANK.list())
        | set(ROLE.list())
        | set(GOD_ALIGNMENT.list())
        | {
            PROSPECT_ROLE_NAME,
            BLACKLISTED_ROLE_NAME,
            BANNED_ROLE_NAME,
        }
    )


def _resolve_tracked_discord_roles(
    guild: discord.Guild, member: discord.Member
) -> list[discord.Role]:
    tracked = _get_tracked_role_names()
    return [r for r in member.roles if r.name in tracked]


@dataclass
class StepResult:
    added_roles: list[str] = field(default_factory=list)
    removed_roles: list[str] = field(default_factory=list)
    nick_set: bool = False
    nick_cleared: bool = False
    errors: list[str] = field(default_factory=list)

    def to_changelog_lines(self) -> list[str]:
        lines = []
        if self.added_roles:
            lines.append(f"added {len(self.added_roles)} role(s) to new")
        if self.removed_roles:
            lines.append(f"removed {len(self.removed_roles)} role(s) from old")
        if self.nick_set:
            lines.append("set new nickname")
        if self.nick_cleared:
            lines.append("cleared old nickname")
        if self.errors:
            lines.append(f"{len(self.errors)} error(s)")
        return lines


class ChangeDiscordAccountView(View):
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
        self.old_user: Optional[discord.Member] = None
        self.new_user: Optional[discord.Member] = None
        self._sync_button_state()

    async def on_timeout(self) -> None:
        await self._delete_message()
        return await super().on_timeout()

    async def _delete_message(self) -> None:
        if self.message:
            try:
                await self.message.delete()
            except (Forbidden, HTTPException):
                pass

    def _sync_button_state(self) -> None:
        can_continue = (
            self.old_user is not None
            and self.new_user is not None
            and self.old_user.id != self.new_user.id
        )
        for child in self.children:
            if (
                isinstance(child, discord.ui.Button)
                and child.custom_id == "change_discord_continue"
            ):
                child.disabled = not can_continue

    def _build_embed(self) -> discord.Embed:
        description = (
            "Select the old account currently linked to the member, and "
            "the new account that they want to take over.\n\nAll tracked "
            "**roles** will be copied over and removed from the old account. Their "
            "**nickname** will be transfered to the new account and removed from the old."
            "\n\nUsing this tool preserves all account history. If an error occurs "
            "**do not** manually change the accounts. Notify relevant admin."
        )
        if self.old_user or self.new_user:
            description += "\n---\n**Selected:**"
            if self.old_user:
                description += f"\nOLD: {self.old_user.mention} (`{self.old_user.id}`)"
            if self.new_user:
                description += f"\nNEW: {self.new_user.mention} (`{self.new_user.id}`)"

        return build_response_embed(
            ":repeat: Change Discord Account",
            description,
            discord.Colour.blue(),
        )

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="Select **old** account...",
        min_values=1,
        max_values=1,
        row=0,
    )
    async def old_account_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.UserSelect,
    ):
        self.old_user = select.values[0]
        if self.new_user and self.new_user.id == self.old_user.id:
            self.new_user = None
        self._sync_button_state()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="Select **new** account...",
        min_values=1,
        max_values=1,
        row=1,
    )
    async def new_account_select(
        self,
        interaction: discord.Interaction,
        select: discord.ui.UserSelect,
    ):
        self.new_user = select.values[0]
        if self.old_user and self.old_user.id == self.new_user.id:
            self.old_user = None
        self._sync_button_state()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @discord.ui.button(
        label="Continue",
        style=discord.ButtonStyle.green,
        custom_id="change_discord_continue",
        row=2,
    )
    async def continue_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not self.old_user or not self.new_user:
            return
        if self.old_user.id == self.new_user.id:
            await interaction.response.send_message(
                "OLD and NEW must be different Discord accounts.",
                ephemeral=True,
            )
            return

        self._sync_button_state()
        for child in self.children:
            if isinstance(child, discord.ui.Item):
                child.disabled = True
        await interaction.response.edit_message(view=self)

        admin_db_id = None
        try:
            async with db.get_session() as session:
                service = create_member_service(session)
                admin = await service.get_member_by_discord_id(interaction.user.id)
                if admin:
                    admin_db_id = admin.id
        except Exception as e:
            logger.error(f"Could not resolve admin DB id: {e}")

        confirm_view = ChangeDiscordAccountConfirmView(
            old_user=self.old_user,
            new_user=self.new_user,
            guild=self.guild,
            report_channel=self.report_channel,
            admin_db_id=admin_db_id,
        )
        try:
            await interaction.edit_original_response(
                embed=confirm_view.build_embed(),
                view=confirm_view,
            )
            confirm_view.message = await interaction.original_response()
        except Exception as e:
            logger.error(f"Failed to swap to confirm view: {e}")

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.grey,
        custom_id="change_discord_cancel",
        row=2,
    )
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self._delete_message()
        if not interaction.response.is_done():
            await interaction.response.send_message("Cancelled.", ephemeral=True)


class ChangeDiscordAccountConfirmView(View):
    def __init__(
        self,
        *,
        old_user: discord.Member,
        new_user: discord.Member,
        guild: discord.Guild,
        report_channel: discord.TextChannel,
        admin_db_id: Optional[str],
    ):
        super().__init__(timeout=VIEW_TIMEOUT_SECONDS)
        self.old_user = old_user
        self.new_user = new_user
        self.guild = guild
        self.report_channel = report_channel
        self.admin_db_id = admin_db_id
        self.message: Optional[discord.Message] = None
        self.completed = False

    async def on_timeout(self) -> None:
        if self.message and not self.completed:
            try:
                await self.message.delete()
            except (Forbidden, HTTPException):
                pass
        return await super().on_timeout()

    def build_embed(self) -> discord.Embed:
        old_tracked = _resolve_tracked_discord_roles(self.guild, self.old_user)
        new_tracked = _resolve_tracked_discord_roles(self.guild, self.new_user)

        to_add = [r for r in old_tracked if r not in new_tracked]
        to_remove = [r for r in old_tracked if r in self.old_user.roles]

        removing_list = ", ".join(r.name for r in to_remove) if to_remove else "_none_"
        adding_list = ", ".join(r.name for r in to_add) if to_add else "_none_"

        description = (
            f"**OLD:** {self.old_user.mention} (`{self.old_user.id}`)\n"
            f"{EMPTY_SPACE}**Removing roles** ({len(to_remove)}): {removing_list}\n\n"
            f"**NEW:** {self.new_user.mention} (`{self.new_user.id}`)\n"
            f"{EMPTY_SPACE}**Adding roles** ({len(to_add)}): {adding_list}"
        )

        return build_response_embed(
            ":warning: Confirm Discord Account Change",
            description,
            discord.Colour.orange(),
        )

    @discord.ui.button(
        label="Confirm",
        style=discord.ButtonStyle.danger,
        custom_id="change_discord_confirm",
    )
    @log_method_execution(logger)
    async def confirm_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.completed:
            return
        self.completed = True
        for child in self.children:
            if isinstance(child, discord.ui.Item):
                child.disabled = True
        if not interaction.response.is_done():
            await interaction.response.edit_message(view=self)

        user_embed, channel_text = await _execute_change(
            old_user=self.old_user,
            new_user=self.new_user,
            guild=self.guild,
            admin_db_id=self.admin_db_id,
        )

        if channel_text is not None:
            try:
                await self.report_channel.send(channel_text)
            except (Forbidden, HTTPException) as e:
                logger.error(f"Failed to post result to report channel: {e}")

        try:
            await interaction.edit_original_response(
                embed=user_embed,
                view=None,
            )
        except (Forbidden, HTTPException) as e:
            logger.error(f"Failed to update ephemeral message: {e}")

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.grey,
        custom_id="change_discord_confirm_cancel",
    )
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.completed:
            return
        self.completed = True
        if self.message:
            try:
                await self.message.delete()
            except (Forbidden, HTTPException):
                pass
        if not interaction.response.is_done():
            await interaction.response.send_message("Cancelled.", ephemeral=True)


async def _apply_to_new(
    old_user: discord.Member, new_user: discord.Member, db_nickname: str
) -> StepResult:
    result = StepResult()
    tracked = _resolve_tracked_discord_roles(old_user.guild, old_user)
    new_tracked_names = {r.name for r in new_user.roles}
    to_add = [r for r in tracked if r.name not in new_tracked_names]

    if to_add:
        try:
            await discord_write_with_retry(
                f"add_roles to {new_user.id}",
                new_user.id,
                lambda: new_user.add_roles(
                    *to_add,
                    atomic=False,
                    reason=f"Migrating roles from {old_user} ({old_user.id})",
                ),
            )
            result.added_roles = [r.name for r in to_add]
        except (Forbidden, HTTPException) as e:
            logger.error(f"Failed to add roles to NEW {new_user}: {e}")
            result.errors.append(f"add_roles: {e}")
        member_update_emitter.suppress_next_for(new_user.id, SUPPRESS_DURATION_MS)

    safe_nick = (db_nickname or "").strip()
    if safe_nick and new_user.display_name != safe_nick:
        try:
            await discord_write_with_retry(
                f"set_nickname on {new_user.id}",
                new_user.id,
                lambda: new_user.edit(
                    nick=safe_nick,
                    reason="Clan nickname synced from DB after account swap",
                ),
            )
            result.nick_set = True
        except (Forbidden, HTTPException) as e:
            logger.error(f"Failed to set NEW nickname: {e}")
            result.errors.append(f"set_nickname: {e}")
        member_update_emitter.suppress_next_for(new_user.id, SUPPRESS_DURATION_MS)
    return result


async def _apply_to_old(
    old_user: discord.Member, new_user: discord.Member
) -> StepResult:
    result = StepResult()
    tracked = _resolve_tracked_discord_roles(old_user.guild, old_user)

    if tracked:
        try:
            await discord_write_with_retry(
                f"remove_roles from {old_user.id}",
                old_user.id,
                lambda: old_user.remove_roles(
                    *tracked,
                    atomic=False,
                    reason=f"Tracked roles migrated to {new_user} ({new_user.id})",
                ),
            )
            result.removed_roles = [r.name for r in tracked]
        except (Forbidden, HTTPException) as e:
            logger.error(f"Failed to remove roles from OLD {old_user}: {e}")
            result.errors.append(f"remove_roles: {e}")
        member_update_emitter.suppress_next_for(old_user.id, SUPPRESS_DURATION_MS)

    if old_user.nick:
        try:
            await discord_write_with_retry(
                f"clear_nickname on {old_user.id}",
                old_user.id,
                lambda: old_user.edit(
                    nick=None,
                    reason="Clan nickname migrated to new Discord account",
                ),
            )
            result.nick_cleared = True
        except (Forbidden, HTTPException) as e:
            logger.error(f"Failed to clear OLD nickname: {e}")
            result.errors.append(f"clear_nickname: {e}")
        member_update_emitter.suppress_next_for(old_user.id, SUPPRESS_DURATION_MS)
    return result


def _build_changelog_comment(
    old_user: discord.Member, new_user: discord.Member, step: StepResult
) -> str:
    parts = [f"from <@{old_user.id}> to <@{new_user.id}>"]
    detail = step.to_changelog_lines()
    if detail:
        parts.append("; " + ", ".join(detail))
    if step.errors:
        parts.append(f"; {len(step.errors)} error(s) during discord writes")
    comment = "Discord account reassigned " + "".join(parts)
    if len(comment) > CHANGELOG_COMMENT_MAX_LENGTH:
        original_len = len(comment)
        comment = comment[: CHANGELOG_COMMENT_MAX_LENGTH - 1] + "…"
        logger.warning(
            f"Change discord id changelog comment truncated from "
            f"{original_len} to {len(comment)} chars"
        )
    return comment


def _build_channel_report(
    old_user: discord.Member,
    new_user: discord.Member,
    *,
    label: str = "reassigned",
    reason: Optional[str] = None,
) -> str:
    line = (
        f":bust_in_silhouette: **Discord account {label}:** "
        f"<@{old_user.id}> → <@{new_user.id}>"
    )
    if reason:
        line += f" — {reason}"
    return line


async def _execute_change(
    *,
    old_user: discord.Member,
    new_user: discord.Member,
    guild: discord.Guild,
    admin_db_id: Optional[str],
) -> tuple[discord.Embed, Optional[str]]:
    try:
        async with db.get_session() as session:
            service = create_member_service(session)
            db_member = await service.get_member_by_discord_id(old_user.id)

            if db_member is None:
                return (
                    build_response_embed(
                        ":x: Member not found",
                        f"{old_user.mention} (`{old_user.id}`) is not linked to a "
                        "member in the database.",
                        discord.Colour.red(),
                    ),
                    _build_channel_report(
                        old_user,
                        new_user,
                        label="reassign failed",
                        reason="OLD not linked to a DB member",
                    ),
                )

            collision = await service.get_member_by_discord_id(new_user.id)
            if collision and collision.id != db_member.id:
                return (
                    build_response_embed(
                        ":x: Discord ID already in use",
                        f"{new_user.mention} (`{new_user.id}`) is already linked "
                        f"to member **{collision.nickname}**.",
                        discord.Colour.red(),
                    ),
                    _build_channel_report(
                        old_user,
                        new_user,
                        label="reassign failed",
                        reason=f"NEW already linked to **{collision.nickname}**",
                    ),
                )

            db_nickname = db_member.nickname

        new_step = await _apply_to_new(old_user, new_user, db_nickname)
        old_step = await _apply_to_old(old_user, new_user)
        combined = StepResult(
            added_roles=new_step.added_roles,
            removed_roles=old_step.removed_roles,
            nick_set=new_step.nick_set,
            nick_cleared=old_step.nick_cleared,
            errors=new_step.errors + old_step.errors,
        )

        comment = _build_changelog_comment(old_user, new_user, combined)

        try:
            async with db.get_session() as session:
                service = create_member_service(session)
                await service.change_discord_id(
                    id=db_member.id,
                    new_discord_id=new_user.id,
                    admin_id=admin_db_id,
                    comment=comment,
                )
        except UniqueDiscordIdVolation as e:
            logger.critical(
                f"DB discord_id swap failed after discord writes for "
                f"old={old_user.id} new={new_user.id}: {e}"
            )
            return (
                build_response_embed(
                    ":x: DB swap failed",
                    f"Discord writes completed but the database update failed: "
                    f"`{e}`. Re-run with the same inputs to retry the DB swap.",
                    discord.Colour.red(),
                ),
                _build_channel_report(
                    old_user,
                    new_user,
                    label="reassign failed",
                    reason="DB swap failed — re-run to retry",
                ),
            )
        except IntegrityError as e:
            logger.critical(
                f"DB integrity error during discord_id swap "
                f"old={old_user.id} new={new_user.id}: {e}"
            )
            return (
                build_response_embed(
                    ":x: DB integrity error",
                    f"Discord writes completed but a DB integrity error occurred: "
                    f"`{e}`.",
                    discord.Colour.red(),
                ),
                _build_channel_report(
                    old_user,
                    new_user,
                    label="reassign failed",
                    reason="DB swap failed (integrity error)",
                ),
            )
        except Exception as e:
            logger.critical(
                f"Unexpected DB error during discord_id swap "
                f"old={old_user.id} new={new_user.id}: {e}"
            )
            return (
                build_response_embed(
                    ":x: DB swap failed",
                    f"Discord writes completed but the database update failed: "
                    f"`{e}`. Re-run with the same inputs to retry the DB swap.",
                    discord.Colour.red(),
                ),
                _build_channel_report(
                    old_user,
                    new_user,
                    label="reassign failed",
                    reason="DB swap failed",
                ),
            )

        title = ":white_check_mark: Discord account changed"
        if combined.errors:
            title = ":warning: Discord account changed (with errors)"
            color = discord.Colour.orange()
        else:
            color = discord.Colour.green()

        description = (
            f"**OLD:** {old_user.mention} (`{old_user.id}`)\n"
            f"**NEW:** {new_user.mention} (`{new_user.id}`)"
        )

        channel_text = _build_channel_report(old_user, new_user)
        return build_response_embed(title, description, color), channel_text
    except Exception as e:
        logger.critical(f"Unhandled exception in change discord account: {e}")
        return (
            build_response_embed(
                ":x: Unexpected error",
                f"An unexpected error occurred: `{e}`.",
                discord.Colour.red(),
            ),
            _build_channel_report(
                old_user,
                new_user,
                label="reassign failed",
                reason="unexpected error",
            ),
        )


async def cmd_change_discord_account(
    interaction: discord.Interaction, report_channel: discord.TextChannel
) -> None:
    """Entry point invoked by the admin menu button.."""
    if not interaction.guild:
        return

    await interaction.response.defer(ephemeral=True)

    view = ChangeDiscordAccountView(
        report_channel=report_channel,
        guild=interaction.guild,
    )
    embed = view._build_embed()
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    try:
        view.message = await interaction.original_response()
    except Exception:
        pass
