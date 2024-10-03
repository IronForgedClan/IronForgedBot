import asyncio
import logging
import signal

logger = logging.getLogger(__name__)


# class AsyncSignalHandler:
#     def __init__(self, loop):
#         self.loop = loop
#         self.shutdown_signal = asyncio.Event()  # Async event for shutdown

#         # Register system signal handlers
#         signal.signal(signal.SIGINT, self.handle_signal)
#         signal.signal(signal.SIGTERM, self.handle_signal)

#     def handle_signal(self, signum, frame):
#         """Trigger graceful shutdown when a signal is received."""
#         logger.info(f"Received signal {signum}, initiating shutdown...")
#         self.loop.create_task(self.graceful_shutdown())

#     async def graceful_shutdown(self):
#         """Emit the 'shutdown' event and stop the event loop after cleanup."""
#         logger.info("Emitting 'shutdown' event to all services...")

#         # Emit the shutdown event to notify all subscribed listeners
#         await event_emitter.emit("shutdown")

#         logger.info("All services have cleaned up. Stopping the event loop.")
#         self.shutdown_signal.set()  # Set shutdown event
#         self.loop.stop()  # Stop the event loop


# class SignalHandler:
#     def __init__(self, loop, client: discord.Client):
#         self.client = client
#         self.loop = loop
#         self.shutdown_signal = asyncio.Event()  # Async event used to signal shutdown

#         # Register signal handlers for graceful shutdown
#         signal.signal(signal.SIGINT, self.handle_signal)
#         signal.signal(signal.SIGTERM, self.handle_signal)

#     def handle_signal(self, signum, frame):
#         """
#         Signal handler to set the shutdown event and trigger cleanup.
#         This must remain synchronous, but will trigger async shutdown tasks.
#         """
#         logger.info(f"Received signal {signum}, initiating shutdown...")
#         self.loop.create_task(self.graceful_shutdown())

#     async def graceful_shutdown(self):
#         """
#         Perform async cleanup tasks and stop the event loop after completion.
#         """
#         logger.info("Starting graceful shutdown...")

#         # Example async cleanup tasks
#         await self.cleanup_tasks()

#         logger.info("Cleanup complete, stopping event loop.")
#         self.shutdown_signal.set()  # Trigger shutdown event
#         self.loop.stop()  # Stop the event loop once tasks are done

#     async def cleanup_tasks(self):
#         """
#         Placeholder method for performing async cleanup tasks like closing connections.
#         """
#         logger.info("Performing cleanup tasks...")
#         await STORAGE.shutdown()
#         await remove_all_automations()
#         await HTTP.close()
#         await self.client.close()
#         close_logging()
#         logger.info("Finished
#  cleanup tasks.")

# def __init__(self):
#     self.loop = asyncio.get_event_loop()

#     signal.signal(signal.SIGINT, self.graceful_shutdown)
#     signal.signal(signal.SIGTERM, self.graceful_shutdown)

# def graceful_shutdown(self, signum, frame):
#     logger.info("Received shutdown command, cleaning up...")

#     self.loop.create_task(self.shutdown_services())

# async def shutdown_services(self):
#     tasks = []
#     tasks.append(STORAGE.shutdown())
#     tasks.append(remove_all_automations())
#     tasks.append(HTTP.close())
#     tasks.append(close_logging())

#     await asyncio.gather(*tasks)
#     logger.info("Done. Shutting down.")
#     self.loop.stop()
