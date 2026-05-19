import discord
from reactionmenu import ViewButton, ViewMenu

from ironforgedbot.commands.leaderboard.leaderboard_embeds import _EMBED_TIMEOUT


class LeaderboardMenu(ViewMenu):
    """A ViewMenu subclass that adds a direct page-jump method.

    Used to power the "Find Me" button via ViewButton.ID_CALLER, bypassing the
    interactive page-prompt that ViewButton.ID_GO_TO_PAGE triggers.
    """

    async def jump_to_page(self, page: int) -> None:
        """Jump directly to the given 1-indexed page number.

        Args:
            page: 1-indexed page number to navigate to.

        Note:
            This accesses private reactionmenu internals (_pc, _msg, _determine_kwargs)
            because the library provides no public API for programmatic page navigation.
            Any reactionmenu upgrade should be tested against this method.
        """
        self._pc.index = page - 1
        await self._msg.edit(**self._determine_kwargs(self._pc.current_page))


def build_leaderboard_menu(
    interaction: discord.Interaction,
    embeds: list[discord.Embed],
    caller_page: int | None,
) -> LeaderboardMenu:
    """Construct a LeaderboardMenu with navigation buttons.

    Buttons added (in order):
      ← Back | Find Me (if caller_page is not None) | Next → | ⨯ Close

    Args:
        interaction: The originating Discord interaction.
        embeds: List of embed pages to add to the menu.
        caller_page: 1-indexed page to jump to for "Find Me", or None to omit the button.

    Returns:
        A configured LeaderboardMenu ready to start.
    """
    menu = LeaderboardMenu(
        interaction,
        menu_type=ViewMenu.TypeEmbed,
        show_page_director=False,
        timeout=_EMBED_TIMEOUT,
        delete_on_timeout=True,
    )

    for embed in embeds:
        menu.add_page(embed)

    menu.add_button(
        ViewButton(
            style=discord.ButtonStyle.primary,
            label="← Back",
            custom_id=ViewButton.ID_PREVIOUS_PAGE,
        )
    )

    if caller_page is not None:
        followup = ViewButton.Followup(
            details=ViewButton.Followup.set_caller_details(
                menu.jump_to_page, caller_page
            )
        )
        menu.add_button(
            ViewButton(
                style=discord.ButtonStyle.success,
                label=f"Find {interaction.user.display_name}",
                custom_id=ViewButton.ID_CALLER,
                followup=followup,
            )
        )

    menu.add_button(
        ViewButton(
            style=discord.ButtonStyle.primary,
            label="Next →",
            custom_id=ViewButton.ID_NEXT_PAGE,
        )
    )
    menu.add_button(
        ViewButton(
            style=discord.ButtonStyle.danger,
            label="⨯ Close",
            custom_id=ViewButton.ID_END_SESSION,
        )
    )

    return menu
