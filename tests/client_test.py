import asyncio
import signal
import unittest
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import discord

from ironforgedbot.client import DiscordClient
from ironforgedbot.common.roles import ROLE
from ironforgedbot.common.ranks import RANK


class ClientTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_intents = Mock(spec=discord.Intents)
        self.mock_guild = Mock(spec=discord.Object)
        self.mock_guild.id = 123456789
        self.client = DiscordClient(intents=self.mock_intents, upload=True, guild=self.mock_guild)

    def test_init_creates_client_with_correct_attributes(self):
        self.assertEqual(self.client.upload, True)
        self.assertEqual(self.client.guild, self.mock_guild)
        self.assertIsNone(self.client.discord_guild)
        self.assertIsNone(self.client.automations)
        self.assertIsInstance(self.client.effect_lock, asyncio.Lock)

    def test_tree_property_getter_and_setter(self):
        mock_tree = Mock(spec=discord.app_commands.CommandTree)
        
        self.client.tree = mock_tree
        
        self.assertEqual(self.client.tree, mock_tree)
        self.assertEqual(self.client._tree, mock_tree)

    @patch("ironforgedbot.client.logger")
    def test_handle_signal_initiates_shutdown(self, mock_logger):
        mock_loop = Mock()
        self.client.loop = mock_loop
        
        def mock_graceful_shutdown():
            return Mock()
        
        self.client.graceful_shutdown = mock_graceful_shutdown
        
        self.client.handle_signal(signal.SIGTERM, None)
        
        mock_logger.info.assert_called_with("Received signal 15, initiating shutdown...")
        mock_loop.call_soon_threadsafe.assert_called_once()

    def test_is_discord_internal_task_identifies_internal_tasks(self):
        mock_task = Mock()
        mock_coro = Mock()
        mock_coro.__qualname__ = "Client.run.<locals>.runner"
        mock_task.get_coro.return_value = mock_coro
        
        result = self.client.is_discord_internal_task(mock_task)
        
        self.assertTrue(result)

    def test_is_discord_internal_task_identifies_external_tasks(self):
        mock_task = Mock()
        mock_coro = Mock()
        mock_coro.__qualname__ = "custom_task"
        mock_task.get_coro.return_value = mock_coro
        
        result = self.client.is_discord_internal_task(mock_task)
        
        self.assertFalse(result)

    def test_is_discord_internal_task_handles_missing_qualname(self):
        mock_task = Mock()
        mock_coro = Mock(spec=[])
        mock_task.get_coro.return_value = mock_coro
        
        result = self.client.is_discord_internal_task(mock_task)
        
        self.assertFalse(result)

    @patch("ironforgedbot.client.STATE")
    @patch("ironforgedbot.client.event_emitter")
    @patch("ironforgedbot.client.db")
    @patch("ironforgedbot.client.asyncio.all_tasks")
    @patch("ironforgedbot.client.asyncio.current_task")
    @patch("ironforgedbot.client.logger")
    async def test_graceful_shutdown_completes_successfully(self, mock_logger, mock_current_task, 
                                                          mock_all_tasks, mock_db, mock_emitter, mock_state):
        mock_state.state = {}
        mock_current_task.return_value = Mock()
        mock_all_tasks.return_value = [mock_current_task.return_value]
        mock_db.dispose = AsyncMock()
        mock_emitter.emit = AsyncMock()
        self.client.close = AsyncMock()
        self.client.automations = Mock()
        self.client.automations.stop = AsyncMock()
        
        await self.client.graceful_shutdown()
        
        self.assertTrue(mock_state.state["is_shutting_down"])
        mock_db.dispose.assert_called_once()
        self.client.automations.stop.assert_called_once()
        mock_emitter.emit.assert_called_once_with("shutdown")
        self.client.close.assert_called_once()

    @patch("ironforgedbot.client.STATE")
    @patch("ironforgedbot.client.populate_emoji_cache")
    async def test_setup_hook_loads_state_and_syncs_commands(self, mock_populate_emoji, mock_state):
        mock_state.load_state = AsyncMock()
        mock_tree = Mock()
        mock_tree.copy_global_to = Mock()
        mock_tree.sync = AsyncMock()
        mock_emojis = [Mock(), Mock()]
        self.client._tree = mock_tree
        self.client.fetch_application_emojis = AsyncMock(return_value=mock_emojis)
        
        await self.client.setup_hook()
        
        mock_state.load_state.assert_called_once()
        mock_tree.copy_global_to.assert_called_once_with(guild=self.mock_guild)
        mock_tree.sync.assert_called_once_with(guild=self.mock_guild)
        mock_populate_emoji.assert_called_once_with(mock_emojis)

    @patch("ironforgedbot.client.STATE")
    @patch("ironforgedbot.client.populate_emoji_cache")
    async def test_setup_hook_skips_sync_when_upload_false(self, mock_populate_emoji, mock_state):
        mock_state.load_state = AsyncMock()
        mock_tree = Mock()
        mock_tree.copy_global_to = Mock()
        mock_tree.sync = AsyncMock()
        self.client.upload = False
        self.client._tree = mock_tree
        self.client.fetch_application_emojis = AsyncMock(return_value=[])
        
        await self.client.setup_hook()
        
        mock_state.load_state.assert_called_once()
        mock_tree.copy_global_to.assert_not_called()
        mock_tree.sync.assert_not_called()

    @patch("ironforgedbot.client.logger")
    async def test_on_connect_logs_message(self, mock_logger):
        await self.client.on_connect()
        
        mock_logger.info.assert_called_once_with("Bot connected to Discord")

    @patch("ironforgedbot.client.logger")
    async def test_on_reconnect_logs_message(self, mock_logger):
        await self.client.on_reconnect()
        
        mock_logger.info.assert_called_once_with("Bot re-connected to Discord")

    @patch("ironforgedbot.client.logger")
    async def test_on_disconnect_logs_message(self, mock_logger):
        await self.client.on_disconnect()
        
        mock_logger.info.assert_called_once_with("Bot has disconnected from Discord")

    @patch("ironforgedbot.client.CONFIG")
    @patch("ironforgedbot.client.IronForgedAutomations")
    async def test_on_ready_sets_presence_and_automations(self, mock_automations_class, mock_config):
        mock_config.GUILD_ID = self.mock_guild.id
        mock_user = Mock()
        mock_user.display_name = "TestBot"
        mock_user.id = 987654321
        
        with patch.object(DiscordClient, 'user', new_callable=PropertyMock) as mock_user_prop:
            mock_user_prop.return_value = mock_user
            self.client.change_presence = AsyncMock()
            self.client.get_guild = Mock(return_value=Mock())
            mock_automations_instance = Mock()
            mock_automations_class.return_value = mock_automations_instance
            
            await self.client.on_ready()
            
            self.client.change_presence.assert_called_once()
            call_args = self.client.change_presence.call_args[1]
            self.assertEqual(call_args["activity"].type, discord.ActivityType.listening)
            self.assertEqual(call_args["activity"].name, "Sea Shanty 2")
            self.assertEqual(self.client.automations, mock_automations_instance)

    @patch("ironforgedbot.client.sys.exit")
    @patch("ironforgedbot.client.logger")
    async def test_on_ready_exits_when_no_user(self, mock_logger, mock_exit):
        with patch.object(DiscordClient, 'user', new_callable=PropertyMock) as mock_user_prop:
            mock_user_prop.return_value = None
            mock_exit.side_effect = SystemExit(1)
            
            with self.assertRaises(SystemExit):
                await self.client.on_ready()
            
            mock_logger.critical.assert_called_once_with("Error logging into discord server")
            mock_exit.assert_called_once_with(1)

    @patch("ironforgedbot.client.CONFIG")
    @patch("ironforgedbot.client.get_text_channel")
    @patch("ironforgedbot.client.nickname_change")
    async def test_on_member_update_handles_nickname_change(self, mock_nickname_change, 
                                                          mock_get_channel, mock_config):
        mock_config.AUTOMATION_CHANNEL_ID = 555666777
        mock_channel = AsyncMock()
        mock_get_channel.return_value = mock_channel
        mock_nickname_change.return_value = AsyncMock()
        
        mock_before = Mock(spec=discord.Member)
        mock_before.nick = "OldNick"
        mock_before.roles = []
        mock_before.guild = Mock()
        
        mock_after = Mock(spec=discord.Member)
        mock_after.nick = "NewNick"
        mock_after.roles = []
        
        await self.client.on_member_update(mock_before, mock_after)
        
        mock_nickname_change.assert_called_once_with(mock_channel, mock_before, mock_after)

    @patch("ironforgedbot.client.CONFIG")
    @patch("ironforgedbot.client.get_text_channel")
    @patch("ironforgedbot.client.add_member_role")
    async def test_on_member_update_handles_member_role_added(self, mock_add_member_role,
                                                            mock_get_channel, mock_config):
        mock_config.AUTOMATION_CHANNEL_ID = 555666777
        mock_channel = AsyncMock()
        mock_get_channel.return_value = mock_channel
        mock_add_member_role.return_value = AsyncMock()
        
        mock_role = Mock()
        mock_role.name = ROLE.MEMBER
        
        mock_before = Mock(spec=discord.Member)
        mock_before.nick = "TestUser"
        mock_before.roles = []
        mock_before.guild = Mock()
        
        mock_after = Mock(spec=discord.Member)
        mock_after.nick = "TestUser"
        mock_after.roles = [mock_role]
        
        await self.client.on_member_update(mock_before, mock_after)
        
        mock_add_member_role.assert_called_once_with(mock_channel, mock_after)

    @patch("ironforgedbot.client.CONFIG")
    @patch("ironforgedbot.client.get_text_channel")
    @patch("ironforgedbot.client.logger")
    async def test_on_member_update_handles_missing_channel(self, mock_logger, 
                                                          mock_get_channel, mock_config):
        mock_config.AUTOMATION_CHANNEL_ID = 555666777
        mock_get_channel.return_value = None
        
        mock_before = Mock(spec=discord.Member)
        mock_before.guild = Mock()
        mock_after = Mock(spec=discord.Member)
        
        await self.client.on_member_update(mock_before, mock_after)
        
        mock_logger.error.assert_called_once_with("Unable to select report channel")