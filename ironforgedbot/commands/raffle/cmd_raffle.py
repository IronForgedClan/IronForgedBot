import io
import logging
import random
from typing import Any, Optional, Tuple

import discord
from discord.ui import Button, Modal, TextInput, View
from PIL import Image, ImageDraw, ImageFont

from ironforgedbot.common.helpers import (
    find_emoji,
    find_member_by_nickname,
    normalize_discord_string,
)
from ironforgedbot.common.responses import build_response_embed, send_error_response
from ironforgedbot.common.roles import ROLE, check_member_has_role
from ironforgedbot.common.text_formatters import text_bold
from ironforgedbot.decorators import require_role
from ironforgedbot.state import STATE
from ironforgedbot.storage.sheets import STORAGE
from ironforgedbot.storage.types import StorageError

logger = logging.getLogger(__name__)


@require_role(ROLE.MEMBER, ephemeral=True)
async def cmd_raffle(interaction: discord.Interaction):
    """Play or control the raffle"""
    file = await build_winner_image_file("oxore", 5105000)
    return await interaction.followup.send(file=file)

    embed = await build_embed(interaction)
    if not embed:
        return

    menu = build_menu(interaction)
    menu.message = await interaction.followup.send(embed=embed, view=menu)


async def build_winner_image_file(winner_name: str, winnings: int) -> discord.File:
    image_path = "img/raffle_winner.jpeg"

    def calculate_position(
        text,
        font: ImageFont.FreeTypeFont,
    ) -> Tuple[float, float]:
        text = str(text)
        bbox = font.getbbox(text)
        text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        image_width, image_height = img.size
        x = (image_width - text_width) // 2
        y = (image_height - text_height) // 2

        return x, y

    def draw_text_with_outline(
        draw: ImageDraw.Draw,
        x: float,
        y: float,
        text: str,
        font: ImageFont.FreeTypeFont,
        outline_color: Any = "black",
        fill_color: Any = "yellow",
        outline_width: int = 2,
    ):
        for offset_x, offset_y in [
            (-outline_width, 0),
            (outline_width, 0),
            (0, -outline_width),
            (0, outline_width),
            (-outline_width, -outline_width),
            (-outline_width, outline_width),
            (outline_width, -outline_width),
            (outline_width, outline_width),
        ]:
            draw.text((x + offset_x, y + offset_y), text, font=font, fill=outline_color)

        draw.text((x, y), text, font=font, fill=fill_color)

    with Image.open(image_path) as img:
        draw = ImageDraw.Draw(img)

        # draw winner name
        font = ImageFont.truetype("fonts/runescape.ttf", size=85)
        x, y = calculate_position(winner_name, font)
        y = y - 65  # offset

        draw_text_with_outline(draw, x, y, winner_name, font)

        # draw winner quantity with icon
        spacing = 10
        offset = 90
        winnings_text = f"{winnings:,}"
        font = ImageFont.truetype("fonts/runescape.ttf", size=40)

        icon = Image.open("img/ingot_icon.png").convert("RGBA")
        icon = icon.resize((35, 35))
        icon_width, icon_height = icon.size

        text_bbox = font.getbbox(winnings_text)
        text_width, text_height = (
            text_bbox[2] - text_bbox[0],
            text_bbox[3] - text_bbox[1],
        )

        total_width = text_width + spacing + icon_width
        image_width = img.width
        x_start = (image_width - total_width) // 2

        # Calculate positions
        icon_x = x_start
        icon_y = (y + (text_height - icon_height) // 2) + offset
        text_x = x_start + icon_width + spacing
        text_y = y + offset

        x, y = calculate_position(winnings_text, font)
        y = y + 20  # offset

        draw_text_with_outline(draw, text_x, text_y, winnings_text, font)
        img.paste(icon, (icon_x, icon_y), mask=icon)

        # Return discord.File
        with io.BytesIO() as image_binary:
            img.save(image_binary, "PNG")
            image_binary.seek(0)
            return discord.File(fp=image_binary, filename="raffle_winner.png")


async def build_embed(interaction: discord.Interaction):
    ticket_icon = find_emoji(None, "Raffle_Ticket")
    ingot_icon = find_emoji(None, "Ingot")
    ticket_price = STATE.state["raffle_price"]
    embed_color = (
        discord.Colour.green() if STATE.state["raffle_on"] else discord.Colour.red()
    )

    try:
        all_tickets = await STORAGE.read_raffle_tickets()
    except StorageError as error:
        return await send_error_response(
            interaction, f"Encountered error ending raffle: {error}"
        )

    my_ticket_count = 0
    total_tickets = 0
    prize_pool = 0

    for id, qty in all_tickets.items():
        if id == interaction.user.id:
            my_ticket_count = qty

        total_tickets += qty

    prize_pool = int(total_tickets * (STATE.state["raffle_price"] / 2))

    embed = build_response_embed(
        title=f"{ticket_icon} Iron Forged Raffle",
        description="",
        color=embed_color,
    )
    embed.add_field(
        name="Raffle Status",
        value="🟢 ONLINE" if STATE.state["raffle_on"] else "🔴 OFFLINE",
        inline=False,
    )
    if STATE.state["raffle_on"]:
        embed.add_field(
            name="Ticket Price",
            value=f"{ingot_icon} {ticket_price:,}",
            inline=True,
        )
        embed.add_field(
            name="My Tickets", value=f"{ticket_icon} {my_ticket_count:,}", inline=True
        )
        embed.add_field(
            name="Prize Pool", value=f"{ingot_icon} {prize_pool:,}", inline=True
        )

    embed.set_thumbnail(
        url="https://oldschool.runescape.wiki/images/thumb/Mounted_coins_built.png/250px-Mounted_coins_built.png"
    )

    return embed


def build_menu(interaction: discord.Interaction):
    assert interaction.guild
    member = interaction.guild.get_member(interaction.user.id)
    assert member
    is_admin = check_member_has_role(member, ROLE.LEADERSHIP, or_higher=True)

    return RaffleMenuView(is_admin)


class RaffleMenuView(View):
    def __init__(self, is_admin=False):
        super().__init__(timeout=60)
        self.message: Optional[discord.Message] = None

        self.add_item(
            Button(
                label="Buy Tickets",
                style=discord.ButtonStyle.primary,
                emoji="🎫",
                disabled=False if STATE.state["raffle_on"] else True,
                custom_id="buy_tickets",
                row=0,
            )
        )

        if is_admin:
            self.add_item(
                Button(
                    label="End Raffle",
                    style=discord.ButtonStyle.red,
                    custom_id="end_raffle",
                    disabled=False if STATE.state["raffle_on"] else True,
                    row=1,
                )
            )

            self.add_item(
                Button(
                    label="Start Raffle",
                    style=discord.ButtonStyle.green,
                    custom_id="start_raffle",
                    disabled=True if STATE.state["raffle_on"] else False,
                    row=1,
                )
            )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.data is not None:
            custom_id = interaction.data.get("custom_id", None)

            if custom_id == "buy_tickets":
                await self.handle_buy_tickets(interaction)
            if custom_id == "start_raffle":
                await self.handle_start_raffle(interaction)
            if custom_id == "end_raffle":
                await self.handle_end_raffle(interaction)

        return await super().interaction_check(interaction)

    async def on_timeout(self) -> None:
        if self.message:
            # await self.message.delete()
            await self.message.edit(view=None)

        return await super().on_timeout()

    async def handle_buy_tickets(self, interaction: discord.Interaction):
        modal = BuyTicketModal()
        await interaction.response.send_modal(modal)

    async def handle_start_raffle(self, interaction: discord.Interaction):
        if not self.message:
            return

        await interaction.response.send_modal(StartRaffleModal())
        await self.message.edit(
            embed=await build_embed(interaction), view=build_menu(interaction)
        )

    async def handle_end_raffle(self, interaction: discord.Interaction):
        assert interaction.guild
        STATE.state["raffle_on"] = False

        try:
            current_tickets = await STORAGE.read_raffle_tickets()
        except StorageError as error:
            await send_error_response(
                interaction, f"Encountered error ending raffle: {error}"
            )
            return

        try:
            members = await STORAGE.read_members()
        except StorageError as error:
            await send_error_response(
                interaction, f"Encountered error reading current members: {error}"
            )
            return

        await interaction.response.edit_message(
            embed=await build_embed(interaction), view=build_menu(interaction)
        )

        # Calculate valid entries
        current_members = {}
        for member in members:
            current_members[member.id] = member.runescape_name

        entries = []
        for id, ticket_count in current_tickets.items():
            # Ignore members who have left the clan since buying tickets
            if current_members.get(id) is not None:
                entries.extend([current_members.get(id)] * ticket_count)

        logger.info(entries)

        # Calculate winner
        winner = entries[random.randrange(0, len(entries))]
        winning_discord_member = find_member_by_nickname(interaction.guild, winner)
        winnings = len(entries) * (STATE.state["raffle_price"] / 2)

        # Award winnings
        try:
            member = await STORAGE.read_member(
                normalize_discord_string(winning_discord_member.display_name)
            )
        except StorageError as error:
            return await send_error_response(interaction, str(error))

        if member is None:
            return await send_error_response(
                interaction,
                f"Member '{winning_discord_member.display_name}' not found in storage.",
            )

        member.ingots += winnings

        try:
            await STORAGE.update_members(
                [member],
                interaction.user.display_name,
                note=f"[BOT] Raffle winnings ({winnings:,})",
            )
        except StorageError as error:
            logger.error(error)
            await send_error_response(interaction, "Error updating ingots.")

        # Cleanup
        try:
            await STORAGE.delete_raffle_tickets(
                normalize_discord_string(interaction.user.display_name).lower()
            )
        except StorageError as error:
            return await send_error_response(
                interaction, f"Encountered error clearing ticket storage: {error}"
            )

        # Announce winner
        ticket_icon = find_emoji(None, "Raffle_Ticket")
        ingot_icon = find_emoji(None, "Ingot")
        file = await build_winner_image_file(winner)

        return await interaction.followup.send(
            (
                f"## {ticket_icon} Congratulations {winning_discord_member.mention}!!\n"
                f"You have won {ingot_icon} {text_bold(f"{winnings:,}")} ingots "
                f"out of {ticket_icon} {text_bold(f"{len(entries):,}")} entries!"
            ),
            file=file,
        )


class StartRaffleModal(Modal):
    def __init__(self):
        super().__init__(title="Start Raffle")

        self.ticket_price = TextInput(
            label="Price per ticket",
            placeholder="5000",
            required=True,
            style=discord.TextStyle.short,
        )

        self.add_item(self.ticket_price)

    async def on_submit(self, interaction: discord.Interaction):
        price = self.ticket_price.value

        if not price.isdigit():
            await interaction.response.send_message("Invalid input.", ephemeral=True)

        STATE.state["raffle_on"] = True
        STATE.state["raffle_price"] = int(price)

        await interaction.response.send_message(
            f"## Starting Raffle\nTicket Price: {int(price):,}", ephemeral=True
        )


class BuyTicketModal(Modal):
    def __init__(self):
        super().__init__(title="Buy Raffle Tickets")

        self.ticket_qty = TextInput(
            label="How many tickets?",
            placeholder="10",
            max_length=10,
            required=True,
            style=discord.TextStyle.short,
        )

        self.add_item(self.ticket_qty)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        qty = self.ticket_qty.value
        caller = normalize_discord_string(interaction.user.display_name)

        if not qty.isdigit():
            return await send_error_response(
                interaction, "Invalid quantity of tickets entered."
            )

        qty = int(qty)
        if qty < 1:
            return await send_error_response(
                interaction, "Invalid quantity of tickets entered."
            )

        try:
            member = await STORAGE.read_member(caller)
        except StorageError as error:
            return await send_error_response(
                interaction, f"Encountered error reading member from storage: {error}"
            )

        if member is None:
            return await send_error_response(
                interaction,
                f"{caller} not found in storage, please reach out to leadership.",
            )

        cost = qty * STATE.state["raffle_price"]
        if cost > member.ingots:
            return await send_error_response(
                interaction,
                f"{caller} does not have enough ingots for {qty:,} tickets.\n"
                + f"Cost: {cost:,}, current ingots: {member.ingots:,}",
            )

        logger.info(f"Buying {qty:,} tickets for {caller}")
        member.ingots -= cost
        try:
            await STORAGE.update_members([member], caller, note="Buy raffle tickets")
        except StorageError as error:
            logger.error(error)
            return await send_error_response(
                interaction, "Encountered error updating member ingot count."
            )

        try:
            await STORAGE.add_raffle_tickets(member.id, qty)
        except StorageError as error:
            logger.error(error)
            return await send_error_response(
                interaction,
                "Encountered error saving raffle tickets. "
                "Ingots have been deducted, please contact a member of staff.",
            )

        ticket_icon = find_emoji(None, "Raffle_Ticket")
        ingot_icon = find_emoji(None, "Ingot")
        embed = build_response_embed(
            title=f"{ticket_icon} Raffle Ticket Purchase",
            description=(
                f"{text_bold(caller)} just bought {ticket_icon} {text_bold(f"{qty:,}")} "
                f"raffle ticket(s)\nfor {ingot_icon} {text_bold(f"{cost:,}")}."
            ),
            color=discord.Colour.gold(),
        )

        await interaction.followup.send(embed=embed)
