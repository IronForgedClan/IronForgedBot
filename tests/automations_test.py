import asyncio
import unittest
import warnings
from unittest.mock import AsyncMock, Mock, patch

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ironforgedbot.automations import IronForgedAutomations


class TestIronForgedAutomations(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        """Suppress AsyncMock coroutine warnings for this test class."""
        warnings.filterwarnings(
            "ignore",
            message="coroutine.*AsyncMockMixin.*was never awaited",
            category=RuntimeWarning
        )
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_guild = Mock(spec=discord.Guild)
        self.mock_guild.id = 123456789
        
        self.mock_channel = Mock(spec=discord.TextChannel)
        self.mock_channel.send = AsyncMock()
        
        # Track automations for cleanup
        self.automations_to_cleanup = []

    def tearDown(self):
        """Clean up after each test method."""
        # Clean up any automations that were created
        for automation in self.automations_to_cleanup:
            try:
                if hasattr(automation, 'scheduler') and automation.scheduler.running:
                    automation.scheduler.shutdown(wait=False)
            except Exception:
                pass  # Ignore cleanup errors
        self.automations_to_cleanup.clear()

    def create_automation_with_mocks(self):
        """Helper to create automation with all necessary mocks."""
        with patch('ironforgedbot.automations.CONFIG') as mock_config, \
             patch('ironforgedbot.automations.get_text_channel') as mock_get_channel, \
             patch('ironforgedbot.automations.ENVIRONMENT') as mock_env, \
             patch('asyncio.create_task') as mock_create_task, \
             patch('ironforgedbot.automations.job_sync_members') as mock_job_sync, \
             patch('ironforgedbot.automations.AsyncIOScheduler') as mock_scheduler_class, \
             patch.object(IronForgedAutomations, 'setup_automations') as mock_setup:
            
            # Configure mocks
            mock_config.AUTOMATION_CHANNEL_ID = 555666777
            mock_config.BOT_VERSION = "1.0.0"
            mock_config.ENVIRONMENT = "test"
            mock_config.WOM_API_KEY = "test_key"
            mock_config.WOM_GROUP_ID = "test_group"
            mock_get_channel.return_value = self.mock_channel
            mock_env.PRODUCTION = "production"
            
            # Mock create_task to return a completed mock task
            mock_task = Mock()
            mock_task.done.return_value = True
            mock_task.cancelled.return_value = False
            mock_task.exception.return_value = None
            mock_task.result.return_value = None
            mock_create_task.return_value = mock_task
            
            # Mock job_sync_members as a simple function that returns a completed coroutine
            async def mock_job_sync_func(*args, **kwargs):
                pass
            mock_job_sync.side_effect = mock_job_sync_func
            
            # Mock setup_automations as an async function that doesn't create coroutines
            async def mock_setup_func(self):
                pass
            mock_setup.side_effect = mock_setup_func
            
            # Mock the scheduler with proper state management
            mock_scheduler = Mock()
            mock_scheduler.running = True
            mock_scheduler.start = Mock()
            mock_scheduler.pause = Mock()
            mock_scheduler.remove_all_jobs = Mock()
            mock_scheduler.add_job = Mock()
            mock_scheduler.get_jobs = Mock(return_value=[])
            
            # Mock shutdown to change running state
            def shutdown_side_effect(**kwargs):
                mock_scheduler.running = False
            mock_scheduler.shutdown = Mock(side_effect=shutdown_side_effect)
            
            mock_scheduler_class.return_value = mock_scheduler
            
            automation = IronForgedAutomations(self.mock_guild)
            self.automations_to_cleanup.append(automation)
            return automation

    def test_init_creates_automation_with_correct_attributes(self):
        """Test automation initializes with correct attributes and starts scheduler."""
        automation = self.create_automation_with_mocks()
        
        # Verify attributes
        self.assertIsInstance(automation._running_jobs, set)
        self.assertIsInstance(automation._job_lock, asyncio.Lock)
        self.assertEqual(automation._shutdown_timeout, 30.0)
        self.assertIsNotNone(automation.scheduler)
        self.assertEqual(automation.report_channel, self.mock_channel)
        self.assertEqual(automation.discord_guild, self.mock_guild)
        
        # Verify scheduler is started
        self.assertTrue(automation.scheduler.running)
        automation.scheduler.start.assert_called_once()

    @patch('ironforgedbot.automations.sys.exit')
    @patch('ironforgedbot.automations.CONFIG')
    @patch('ironforgedbot.automations.get_text_channel')
    @patch('asyncio.create_task')
    @patch('ironforgedbot.automations.job_sync_members')
    @patch('ironforgedbot.automations.AsyncIOScheduler')
    def test_init_exits_when_no_channel(self, mock_scheduler_class, mock_job_sync, mock_create_task, mock_get_channel, mock_config, mock_exit):
        """Test automation exits when channel cannot be found."""
        mock_config.AUTOMATION_CHANNEL_ID = 555666777
        mock_get_channel.return_value = None
        mock_exit.side_effect = SystemExit(1)
        mock_create_task.return_value = Mock()
        mock_job_sync.return_value = None
        
        # Mock scheduler
        mock_scheduler = Mock()
        mock_scheduler.running = True
        mock_scheduler_class.return_value = mock_scheduler
        
        with self.assertRaises(SystemExit):
            automation = IronForgedAutomations(self.mock_guild)
            self.automations_to_cleanup.append(automation)
        
        mock_exit.assert_called_once_with(1)

    @patch('ironforgedbot.automations.sys.exit')
    @patch('ironforgedbot.automations.CONFIG')
    @patch('ironforgedbot.automations.get_text_channel')
    @patch('asyncio.create_task')
    @patch('ironforgedbot.automations.job_sync_members')
    @patch('ironforgedbot.automations.AsyncIOScheduler')
    def test_init_exits_when_no_guild(self, mock_scheduler_class, mock_job_sync, mock_create_task, mock_get_channel, mock_config, mock_exit):
        """Test automation exits when guild is None."""
        mock_config.AUTOMATION_CHANNEL_ID = 555666777
        mock_get_channel.return_value = self.mock_channel
        mock_exit.side_effect = SystemExit(1)
        mock_create_task.return_value = Mock()
        mock_job_sync.return_value = None
        
        # Mock scheduler
        mock_scheduler = Mock()
        mock_scheduler.running = True
        mock_scheduler_class.return_value = mock_scheduler
        
        with self.assertRaises(SystemExit):
            automation = IronForgedAutomations(None)
            self.automations_to_cleanup.append(automation)
        
        mock_exit.assert_called_once_with(1)

    async def test_stop_shuts_down_gracefully(self):
        """Test graceful shutdown process."""
        automation = self.create_automation_with_mocks()
        
        # Mock wait_for_jobs_to_complete
        automation.wait_for_jobs_to_complete = AsyncMock()
        
        await automation.stop()
        
        # Verify scheduler shutdown was called
        automation.scheduler.shutdown.assert_called_once()
        automation.scheduler.pause.assert_called_once()
        
        # Verify shutdown message sent (check that any version message was sent)
        expected_calls = [call for call in self.mock_channel.send.call_args_list if "now offline" in str(call)]
        self.assertTrue(len(expected_calls) > 0, "Expected offline message to be sent")
        
        # Verify jobs completion was awaited
        automation.wait_for_jobs_to_complete.assert_called_once()

    async def test_stop_handles_errors_gracefully(self):
        """Test stop method handles errors and re-raises them."""
        automation = self.create_automation_with_mocks()
        
        # Mock wait_for_jobs_to_complete to raise an exception
        test_error = Exception("Test error")
        automation.wait_for_jobs_to_complete = AsyncMock(side_effect=test_error)
        
        with self.assertRaises(Exception) as context:
            await automation.stop()
        
        self.assertEqual(context.exception, test_error)

    async def test_wait_for_jobs_to_complete_no_active_jobs(self):
        """Test waiting for jobs when no jobs are active."""
        automation = self.create_automation_with_mocks()
        
        # Ensure no jobs are running
        automation._running_jobs.clear()
        
        await automation.wait_for_jobs_to_complete()
        
        # Should return immediately with no jobs

    @patch('asyncio.wait_for')
    @patch('asyncio.gather')
    async def test_wait_for_jobs_to_complete_with_jobs(self, mock_gather, mock_wait_for):
        """Test waiting for jobs when jobs are running."""
        automation = self.create_automation_with_mocks()
        
        # Add mock jobs
        mock_job1 = Mock()
        mock_job2 = Mock()
        automation._running_jobs.add(mock_job1)
        automation._running_jobs.add(mock_job2)
        
        mock_gather.return_value = []
        mock_wait_for.return_value = []
        
        await automation.wait_for_jobs_to_complete()
        
        # Verify gather was called with the jobs (order doesn't matter since it's a set)
        mock_gather.assert_called_once()
        call_args = mock_gather.call_args
        self.assertEqual(len(call_args[0]), 2)  # Two positional args
        self.assertIn(mock_job1, call_args[0])  # mock_job1 is in the call
        self.assertIn(mock_job2, call_args[0])  # mock_job2 is in the call
        self.assertEqual(call_args[1], {'return_exceptions': True})  # Keyword args
        mock_wait_for.assert_called_once_with(mock_gather.return_value, timeout=30.0)

    async def test_wait_for_jobs_handles_timeout(self):
        """Test waiting for jobs handles timeout by cancelling jobs."""
        automation = self.create_automation_with_mocks()
        
        # Add mock jobs
        mock_job1 = Mock()
        mock_job1.done.return_value = False
        mock_job1.cancel = Mock()
        mock_job2 = Mock()
        mock_job2.done.return_value = True
        
        automation._running_jobs.add(mock_job1)
        automation._running_jobs.add(mock_job2)
        
        # Mock wait_for to raise timeout and test the timeout handling code path
        with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError()), \
             patch('asyncio.gather', return_value=[]):
            
            await automation.wait_for_jobs_to_complete()
        
        # Verify only non-done job was cancelled
        mock_job1.cancel.assert_called_once()

    async def test_track_job_creates_and_tracks_task(self):
        """Test track_job creates task and adds it to tracking set."""
        automation = self.create_automation_with_mocks()
        
        # Clear any existing jobs from init
        automation._running_jobs.clear()
        
        # Mock job function as a simple coroutine
        async def mock_job_func(*args, **kwargs):
            pass
        mock_task = Mock()
        
        with patch('asyncio.create_task', return_value=mock_task) as mock_create_async_task:
            result = await automation.track_job(mock_job_func, "arg1", kwarg1="value1")
        
        # Verify task creation and tracking
        self.assertEqual(result, mock_task)
        self.assertIn(mock_task, automation._running_jobs)
        mock_task.add_done_callback.assert_called_once_with(automation._job_done_callback)

    async def test_track_job_handles_creation_error(self):
        """Test track_job handles task creation errors."""
        automation = self.create_automation_with_mocks()
        
        async def mock_job_func():
            pass
        test_error = Exception("Task creation failed")
        
        with patch('asyncio.create_task', side_effect=test_error):
            with self.assertRaises(Exception) as context:
                await automation.track_job(mock_job_func)
        
        self.assertEqual(context.exception, test_error)

    async def test_job_done_callback_removes_completed_task(self):
        """Test job done callback removes task from tracking set."""
        automation = self.create_automation_with_mocks()
        
        # Create a mock task
        mock_task = Mock()
        mock_task.exception.return_value = None
        automation._running_jobs.add(mock_task)
        
        # Create a mock for the cleanup task that will be created
        mock_cleanup_task = Mock()
        mock_cleanup_task.done.return_value = True
        mock_cleanup_task.cancelled.return_value = False
        mock_cleanup_task.exception.return_value = None
        
        with patch('asyncio.create_task', return_value=mock_cleanup_task) as mock_create_cleanup:
            automation._job_done_callback(mock_task)
        
        # Verify cleanup task was created
        mock_create_cleanup.assert_called_once()

    def test_job_done_callback_handles_runtime_error(self):
        """Test job done callback handles RuntimeError when event loop is closed."""
        automation = self.create_automation_with_mocks()
        
        mock_task = Mock()
        mock_task.exception.return_value = None
        
        with patch('asyncio.create_task', side_effect=RuntimeError("Event loop is closed")):
            # Should not raise an exception
            automation._job_done_callback(mock_task)

    def test_job_wrapper_schedules_tracking(self):
        """Test job wrapper schedules job tracking."""
        automation = self.create_automation_with_mocks()
        
        async def mock_job_func():
            pass
        mock_tracking_task = Mock()
        mock_tracking_task.done.return_value = True
        mock_tracking_task.cancelled.return_value = False
        mock_tracking_task.exception.return_value = None
        
        # Get the wrapper function
        wrapper = automation._job_wrapper(mock_job_func, "arg1", kwarg1="value1")
        
        with patch('asyncio.create_task', return_value=mock_tracking_task) as mock_create_tracking:
            wrapper()
        
        # Verify tracking task was created
        mock_create_tracking.assert_called_once()

    def test_job_wrapper_handles_runtime_error(self):
        """Test job wrapper handles RuntimeError when event loop is closed."""
        automation = self.create_automation_with_mocks()
        
        async def mock_job_func():
            pass
        wrapper = automation._job_wrapper(mock_job_func)
        
        with patch('asyncio.create_task', side_effect=RuntimeError("Event loop is closed")):
            # Should not raise an exception
            wrapper()

    async def test_safe_job_wrapper_executes_successfully(self):
        """Test safe job wrapper executes job function successfully."""
        automation = self.create_automation_with_mocks()
        
        call_args = None
        async def mock_job_func(*args, **kwargs):
            nonlocal call_args
            call_args = (args, kwargs)
        
        await automation._safe_job_wrapper(mock_job_func, "arg1", kwarg1="value1")
        
        # Verify the function was called with correct arguments
        self.assertEqual(call_args, (("arg1",), {"kwarg1": "value1"}))

    async def test_safe_job_wrapper_handles_cancelled_error(self):
        """Test safe job wrapper handles CancelledError appropriately."""
        automation = self.create_automation_with_mocks()
        
        async def mock_job_func():
            raise asyncio.CancelledError()
        
        with self.assertRaises(asyncio.CancelledError):
            await automation._safe_job_wrapper(mock_job_func)

    async def test_safe_job_wrapper_handles_general_exception(self):
        """Test safe job wrapper handles general exceptions and sends notifications."""
        automation = self.create_automation_with_mocks()
        
        test_error = ValueError("Test error")
        async def mock_job_func():
            raise test_error
        
        with self.assertRaises(ValueError):
            await automation._safe_job_wrapper(mock_job_func)
        
        # Verify error notification was sent
        self.mock_channel.send.assert_called_with(
            "⚠️ **Job Error**: `mock_job_func` failed with: `ValueError: Test error`"
        )

    async def test_safe_job_wrapper_handles_notification_error(self):
        """Test safe job wrapper handles error notification failures."""
        automation = self.create_automation_with_mocks()
        
        test_error = ValueError("Test error")
        async def mock_job_func():
            raise test_error
        
        # Mock channel send to fail
        self.mock_channel.send.side_effect = Exception("Channel send failed")
        
        with self.assertRaises(ValueError):
            await automation._safe_job_wrapper(mock_job_func)

    @patch('ironforgedbot.automations.SCORE_CACHE')
    async def test_clear_caches_successful(self, mock_score_cache):
        """Test cache clearing executes successfully."""
        automation = self.create_automation_with_mocks()
        
        # Mock clean method with tracking
        clean_called = False
        async def mock_clean():
            nonlocal clean_called
            clean_called = True
            return "Cache cleaned successfully"
        mock_score_cache.clean = mock_clean
        
        await automation._clear_caches()
        
        # Verify clean was called
        self.assertTrue(clean_called, "SCORE_CACHE.clean should have been called")

    @patch('ironforgedbot.automations.SCORE_CACHE')
    async def test_clear_caches_handles_error(self, mock_score_cache):
        """Test cache clearing handles errors appropriately."""
        automation = self.create_automation_with_mocks()
        
        test_error = Exception("Cache clean failed")
        async def mock_clean():
            raise test_error
        mock_score_cache.clean = mock_clean
        
        with self.assertRaises(Exception) as context:
            await automation._clear_caches()
        
        self.assertEqual(context.exception, test_error)

    @patch('ironforgedbot.automations.random.randint')
    async def test_setup_automations_adds_all_jobs(self, mock_randint):
        """Test setup_automations adds all scheduled jobs correctly."""
        mock_randint.return_value = 25
        
        automation = self.create_automation_with_mocks()
        
        # Clear existing jobs
        automation.scheduler.remove_all_jobs()
        
        await automation.setup_automations()
        
        # Verify 5 jobs were added by checking add_job call count
        self.assertEqual(automation.scheduler.add_job.call_count, 5)
        
        # Verify startup message was sent (check that any version message was sent)
        expected_calls = [call for call in self.mock_channel.send.call_args_list if "now online" in str(call)]
        self.assertTrue(len(expected_calls) > 0, "Expected online message to be sent")

    async def test_scheduler_integration(self):
        """Test integration between scheduler and job tracking."""
        automation = self.create_automation_with_mocks()
        
        # Verify scheduler is properly configured
        self.assertTrue(automation.scheduler.running)
        self.assertIsNotNone(automation.scheduler)
        
        # Test adding a simple job
        test_job_called = asyncio.Event()
        
        async def test_job():
            test_job_called.set()
        
        # Add job to scheduler
        job_wrapper = automation._job_wrapper(test_job)
        automation.scheduler.add_job(job_wrapper, 'date', run_date=None)
        
        # Trigger the job immediately
        job_wrapper()
        
        # Give some time for job to execute
        await asyncio.sleep(0.1)

    def test_automation_cleanup_on_destruction(self):
        """Test automation properly cleans up resources."""
        automation = self.create_automation_with_mocks()
        
        # Verify scheduler is running
        self.assertTrue(automation.scheduler.running)
        
        # Manually shutdown for testing
        automation.scheduler.shutdown(wait=False)
        
        # Verify scheduler is stopped
        self.assertFalse(automation.scheduler.running)

    async def test_concurrent_job_tracking(self):
        """Test concurrent job tracking operations are properly synchronized."""
        automation = self.create_automation_with_mocks()
        automation._running_jobs.clear()
        
        async def mock_job_func(delay):
            await asyncio.sleep(delay)
        
        # Create multiple concurrent jobs
        tasks = []
        for i in range(5):
            task = asyncio.create_task(automation.track_job(mock_job_func, 0.01))
            tasks.append(task)
        
        # Wait for all jobs to be tracked
        tracked_tasks = await asyncio.gather(*tasks)
        
        # Verify all tasks were tracked
        self.assertEqual(len(tracked_tasks), 5)
        for task in tracked_tasks:
            self.assertIn(task, automation._running_jobs)