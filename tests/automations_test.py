import asyncio
import unittest
import warnings
from unittest.mock import AsyncMock, Mock, patch

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ironforgedbot.automations import IronForgedAutomations
from tests.helpers import create_mock_discord_guild


class TestIronForgedAutomations(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        """Suppress async-related warnings for this test class."""
        warnings.filterwarnings(
            "ignore",
            message="coroutine.*AsyncMockMixin.*was never awaited",
            category=RuntimeWarning,
        )
        warnings.filterwarnings(
            "ignore",
            message="coroutine.*IronForgedAutomations.*was never awaited",
            category=RuntimeWarning,
        )
        warnings.filterwarnings(
            "ignore",
            message="coroutine.*cleanup.*was never awaited",
            category=RuntimeWarning,
        )
        warnings.filterwarnings(
            "ignore",
            message="coroutine.*_safe_job_wrapper.*was never awaited",
            category=RuntimeWarning,
        )

    def setUp(self):
        self.mock_guild = create_mock_discord_guild()
        self.mock_guild.id = 123456789

        self.mock_channel = Mock(spec=discord.TextChannel)
        self.mock_channel.send = AsyncMock()

        self.automations_to_cleanup = []

    def tearDown(self):
        for automation in self.automations_to_cleanup:
            try:
                if hasattr(automation, "scheduler") and automation.scheduler.running:
                    automation.scheduler.shutdown(wait=False)
            except Exception:
                pass
        self.automations_to_cleanup.clear()

    def create_automation_with_mocks(self):
        """Create automation with all necessary mocks."""
        with patch("ironforgedbot.automations.CONFIG") as mock_config, patch(
            "ironforgedbot.automations.get_text_channel"
        ) as mock_get_channel, patch(
            "ironforgedbot.automations.ENVIRONMENT"
        ) as mock_env, patch(
            "asyncio.create_task"
        ) as mock_create_task, patch(
            "ironforgedbot.automations.job_sync_members"
        ) as mock_job_sync, patch(
            "ironforgedbot.automations.AsyncIOScheduler"
        ) as mock_scheduler_class, patch.object(
            IronForgedAutomations, "setup_automations"
        ) as mock_setup:

            mock_config.AUTOMATION_CHANNEL_ID = 555666777
            mock_config.BOT_VERSION = "1.0.0"
            mock_config.ENVIRONMENT = "test"
            mock_config.WOM_API_KEY = "test_key"
            mock_config.WOM_GROUP_ID = "test_group"
            mock_get_channel.return_value = self.mock_channel
            mock_env.PRODUCTION = "production"

            mock_task = Mock()
            mock_task.done.return_value = True
            mock_task.cancelled.return_value = False
            mock_task.exception.return_value = None
            mock_task.result.return_value = None
            mock_create_task.return_value = mock_task

            async def mock_job_sync_func(*args, **kwargs):
                pass

            mock_job_sync.side_effect = mock_job_sync_func

            async def mock_setup_func(self):
                pass

            mock_setup.side_effect = mock_setup_func

            mock_scheduler = Mock()
            mock_scheduler.running = True
            mock_scheduler.start = Mock()
            mock_scheduler.pause = Mock()
            mock_scheduler.remove_all_jobs = Mock()
            mock_scheduler.add_job = Mock()
            mock_scheduler.get_jobs = Mock(return_value=[])

            def shutdown_side_effect(**kwargs):
                mock_scheduler.running = False

            mock_scheduler.shutdown = Mock(side_effect=shutdown_side_effect)

            mock_scheduler_class.return_value = mock_scheduler

            automation = IronForgedAutomations(self.mock_guild)
            self.automations_to_cleanup.append(automation)
            return automation

    def test_init_creates_automation_with_correct_attributes(self):
        automation = self.create_automation_with_mocks()

        self.assertIsInstance(automation._running_jobs, set)
        self.assertIsInstance(automation._job_lock, asyncio.Lock)
        self.assertEqual(automation._shutdown_timeout, 30.0)
        self.assertIsNotNone(automation.scheduler)
        self.assertEqual(automation.report_channel, self.mock_channel)
        self.assertEqual(automation.discord_guild, self.mock_guild)
        self.assertTrue(automation.scheduler.running)
        automation.scheduler.start.assert_called_once()

    @patch("ironforgedbot.automations.sys.exit")
    @patch("ironforgedbot.automations.CONFIG")
    @patch("ironforgedbot.automations.get_text_channel")
    @patch("asyncio.create_task")
    @patch("ironforgedbot.automations.job_sync_members")
    @patch("ironforgedbot.automations.AsyncIOScheduler")
    def test_init_exits_when_no_channel(
        self,
        mock_scheduler_class,
        mock_job_sync,
        mock_create_task,
        mock_get_channel,
        mock_config,
        mock_exit,
    ):
        mock_config.AUTOMATION_CHANNEL_ID = 555666777
        mock_get_channel.return_value = None
        mock_exit.side_effect = SystemExit(1)
        mock_create_task.return_value = Mock()
        mock_job_sync.return_value = None

        mock_scheduler = Mock()
        mock_scheduler.running = True
        mock_scheduler_class.return_value = mock_scheduler

        with self.assertRaises(SystemExit):
            automation = IronForgedAutomations(self.mock_guild)
            self.automations_to_cleanup.append(automation)

        mock_exit.assert_called_once_with(1)

    @patch("ironforgedbot.automations.sys.exit")
    @patch("ironforgedbot.automations.CONFIG")
    @patch("ironforgedbot.automations.get_text_channel")
    @patch("asyncio.create_task")
    @patch("ironforgedbot.automations.job_sync_members")
    @patch("ironforgedbot.automations.AsyncIOScheduler")
    def test_init_exits_when_no_guild(
        self,
        mock_scheduler_class,
        mock_job_sync,
        mock_create_task,
        mock_get_channel,
        mock_config,
        mock_exit,
    ):
        mock_config.AUTOMATION_CHANNEL_ID = 555666777
        mock_get_channel.return_value = self.mock_channel
        mock_exit.side_effect = SystemExit(1)
        mock_create_task.return_value = Mock()
        mock_job_sync.return_value = None

        mock_scheduler = Mock()
        mock_scheduler.running = True
        mock_scheduler_class.return_value = mock_scheduler

        with self.assertRaises(SystemExit):
            automation = IronForgedAutomations(None)
            self.automations_to_cleanup.append(automation)

        mock_exit.assert_called_once_with(1)

    async def test_stop_shuts_down_gracefully(self):
        automation = self.create_automation_with_mocks()
        automation.wait_for_jobs_to_complete = AsyncMock()

        await automation.stop()

        automation.scheduler.shutdown.assert_called_once()
        automation.scheduler.pause.assert_called_once()
        expected_calls = [
            call
            for call in self.mock_channel.send.call_args_list
            if "now offline" in str(call)
        ]
        self.assertTrue(len(expected_calls) > 0, "Expected offline message to be sent")
        automation.wait_for_jobs_to_complete.assert_called_once()

    async def test_stop_handles_errors_gracefully(self):
        automation = self.create_automation_with_mocks()
        test_error = Exception("Test error")
        automation.wait_for_jobs_to_complete = AsyncMock(side_effect=test_error)

        with self.assertRaises(Exception) as context:
            await automation.stop()

        self.assertEqual(context.exception, test_error)

    async def test_wait_for_jobs_to_complete_no_active_jobs(self):
        automation = self.create_automation_with_mocks()
        automation._running_jobs.clear()

        await automation.wait_for_jobs_to_complete()

    @patch("asyncio.wait_for")
    @patch("asyncio.gather")
    async def test_wait_for_jobs_to_complete_with_jobs(
        self, mock_gather, mock_wait_for
    ):
        automation = self.create_automation_with_mocks()

        mock_job1 = Mock()
        mock_job2 = Mock()
        automation._running_jobs.add(mock_job1)
        automation._running_jobs.add(mock_job2)

        mock_gather.return_value = []
        mock_wait_for.return_value = []

        await automation.wait_for_jobs_to_complete()

        mock_gather.assert_called_once()
        call_args = mock_gather.call_args
        self.assertEqual(len(call_args[0]), 2)
        self.assertIn(mock_job1, call_args[0])
        self.assertIn(mock_job2, call_args[0])
        self.assertEqual(call_args[1], {"return_exceptions": True})
        mock_wait_for.assert_called_once_with(mock_gather.return_value, timeout=30.0)

    async def test_wait_for_jobs_handles_timeout(self):
        automation = self.create_automation_with_mocks()

        mock_job1 = Mock()
        mock_job1.done.return_value = False
        mock_job1.cancel = Mock()
        mock_job2 = Mock()
        mock_job2.done.return_value = True

        automation._running_jobs.add(mock_job1)
        automation._running_jobs.add(mock_job2)

        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()), patch(
            "asyncio.gather", return_value=[]
        ):
            await automation.wait_for_jobs_to_complete()

        mock_job1.cancel.assert_called_once()

    async def test_track_job_creates_and_tracks_task(self):
        automation = self.create_automation_with_mocks()
        automation._running_jobs.clear()

        async def mock_job_func(*args, **kwargs):
            pass

        mock_task = Mock()

        with patch(
            "ironforgedbot.automations.asyncio.create_task", return_value=mock_task
        ):
            result = await automation.track_job(mock_job_func, "arg1", kwarg1="value1")

        self.assertEqual(result, mock_task)
        self.assertIn(mock_task, automation._running_jobs)
        mock_task.add_done_callback.assert_called_once_with(
            automation._job_done_callback
        )

    async def test_track_job_handles_creation_error(self):
        automation = self.create_automation_with_mocks()

        async def mock_job_func():
            pass

        test_error = Exception("Task creation failed")

        with patch(
            "ironforgedbot.automations.asyncio.create_task", side_effect=test_error
        ):
            with self.assertRaises(Exception) as context:
                await automation.track_job(mock_job_func)

        self.assertEqual(context.exception, test_error)

    async def test_job_done_callback_removes_completed_task(self):
        automation = self.create_automation_with_mocks()

        mock_task = Mock()
        mock_task.exception.return_value = None
        automation._running_jobs.add(mock_task)

        mock_cleanup_task = Mock()
        mock_cleanup_task.done.return_value = True
        mock_cleanup_task.cancelled.return_value = False
        mock_cleanup_task.exception.return_value = None

        with patch(
            "ironforgedbot.automations.asyncio.create_task",
            return_value=mock_cleanup_task,
        ) as mock_create_cleanup:
            automation._job_done_callback(mock_task)

        mock_create_cleanup.assert_called_once()

    def test_job_done_callback_handles_runtime_error(self):
        automation = self.create_automation_with_mocks()

        mock_task = Mock()
        mock_task.exception.return_value = None

        with patch(
            "ironforgedbot.automations.asyncio.create_task",
            side_effect=RuntimeError("Event loop is closed"),
        ):
            automation._job_done_callback(mock_task)

    def test_job_wrapper_schedules_tracking(self):
        automation = self.create_automation_with_mocks()

        async def mock_job_func():
            pass

        mock_tracking_task = Mock()
        mock_tracking_task.done.return_value = True
        mock_tracking_task.cancelled.return_value = False
        mock_tracking_task.exception.return_value = None

        wrapper = automation._job_wrapper(mock_job_func, "arg1", kwarg1="value1")

        with patch(
            "ironforgedbot.automations.asyncio.create_task",
            return_value=mock_tracking_task,
        ) as mock_create_tracking:
            wrapper()

        mock_create_tracking.assert_called_once()

    def test_job_wrapper_handles_runtime_error(self):
        automation = self.create_automation_with_mocks()

        async def mock_job_func():
            pass

        wrapper = automation._job_wrapper(mock_job_func)

        with patch(
            "ironforgedbot.automations.asyncio.create_task",
            side_effect=RuntimeError("Event loop is closed"),
        ):
            wrapper()

    async def test_safe_job_wrapper_executes_successfully(self):
        automation = self.create_automation_with_mocks()

        call_args = None

        async def mock_job_func(*args, **kwargs):
            nonlocal call_args
            call_args = (args, kwargs)

        await automation._safe_job_wrapper(mock_job_func, "arg1", kwarg1="value1")

        self.assertEqual(call_args, (("arg1",), {"kwarg1": "value1"}))

    async def test_safe_job_wrapper_handles_cancelled_error(self):
        automation = self.create_automation_with_mocks()

        async def mock_job_func():
            raise asyncio.CancelledError()

        with self.assertRaises(asyncio.CancelledError):
            await automation._safe_job_wrapper(mock_job_func)

    async def test_safe_job_wrapper_handles_general_exception(self):
        automation = self.create_automation_with_mocks()

        test_error = ValueError("Test error")

        async def mock_job_func():
            raise test_error

        with self.assertRaises(ValueError):
            await automation._safe_job_wrapper(mock_job_func)

        self.mock_channel.send.assert_called_with(
            "⚠️ **Job Error**: `mock_job_func` failed with: `ValueError: Test error`"
        )

    async def test_safe_job_wrapper_handles_notification_error(self):
        automation = self.create_automation_with_mocks()

        test_error = ValueError("Test error")

        async def mock_job_func():
            raise test_error

        self.mock_channel.send.side_effect = Exception("Channel send failed")

        with self.assertRaises(ValueError):
            await automation._safe_job_wrapper(mock_job_func)

    @patch("ironforgedbot.automations.SCORE_CACHE")
    async def test_clear_caches_successful(self, mock_score_cache):
        automation = self.create_automation_with_mocks()

        clean_called = False

        async def mock_clean():
            nonlocal clean_called
            clean_called = True
            return "Cache cleaned successfully"

        mock_score_cache.clean = mock_clean

        await automation._clear_caches()

        self.assertTrue(clean_called, "SCORE_CACHE.clean should have been called")

    @patch("ironforgedbot.automations.SCORE_CACHE")
    async def test_clear_caches_handles_error(self, mock_score_cache):
        automation = self.create_automation_with_mocks()

        test_error = Exception("Cache clean failed")

        async def mock_clean():
            raise test_error

        mock_score_cache.clean = mock_clean

        with self.assertRaises(Exception) as context:
            await automation._clear_caches()

        self.assertEqual(context.exception, test_error)

    @patch("ironforgedbot.automations.random.randint")
    async def test_setup_automations_adds_all_jobs(self, mock_randint):
        mock_randint.return_value = 25

        automation = self.create_automation_with_mocks()
        automation.scheduler.remove_all_jobs()

        await automation.setup_automations()

        self.assertEqual(automation.scheduler.add_job.call_count, 5)
        expected_calls = [
            call
            for call in self.mock_channel.send.call_args_list
            if "now online" in str(call)
        ]
        self.assertTrue(len(expected_calls) > 0, "Expected online message to be sent")

    async def test_scheduler_integration(self):
        automation = self.create_automation_with_mocks()

        self.assertTrue(automation.scheduler.running)
        self.assertIsNotNone(automation.scheduler)

        test_job_called = asyncio.Event()

        async def test_job():
            test_job_called.set()

        job_wrapper = automation._job_wrapper(test_job)
        automation.scheduler.add_job(job_wrapper, "date", run_date=None)
        job_wrapper()

        await asyncio.sleep(0.1)

    def test_automation_cleanup_on_destruction(self):
        automation = self.create_automation_with_mocks()

        self.assertTrue(automation.scheduler.running)

        automation.scheduler.shutdown(wait=False)

        self.assertFalse(automation.scheduler.running)

    async def test_concurrent_job_tracking(self):
        automation = self.create_automation_with_mocks()
        automation._running_jobs.clear()

        async def mock_job_func(delay):
            await asyncio.sleep(delay)

        mock_tasks = [Mock() for _ in range(5)]

        with patch(
            "ironforgedbot.automations.asyncio.create_task", side_effect=mock_tasks
        ):
            tasks = []
            for i in range(5):
                task = await automation.track_job(mock_job_func, 0.01)
                tasks.append(task)

        self.assertEqual(len(tasks), 5)
        for mock_task in mock_tasks:
            self.assertIn(mock_task, automation._running_jobs)
