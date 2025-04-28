from PyQt6.QtCore import QObject, QThread, pyqtSignal, QWaitCondition, QMutex
import requests
from PIL import Image
from io import BytesIO

import aiohttp
import asyncio

from src.utils import get_logger


class AsyncRemoteImageLoader(QObject):
    """Thread to load remote images asynchronously"""

    image_loaded = pyqtSignal(str, bytes)
    error_occurred = pyqtSignal(str, str)

    def __init__(self, urls, max_parralel_reqs: int = 10, images: list = []):
        super().__init__()
        self.urls = urls
        self.loop = None
        self.logger = get_logger(AsyncRemoteImageLoader.__name__)
        self.images = images
        self.max_parralel_reqs = max_parralel_reqs
        self.semaphore = asyncio.Semaphore(self.max_parralel_reqs)
        self.running = True

    async def fetch_one_image(self, session: aiohttp.ClientSession, url, index):
        """Fetch a single image asynchronously"""
        if not self.running:
            return
        try:
            async with session.get(url, timeout=10) as response:
                response.raise_for_status()
                image_bytes = await response.read()
                # image = Image.open(BytesIO(image_bytes))
                self.images[index] = image_bytes
                if index == 0:
                    self.image_loaded.emit(url, image_bytes)

        except Exception as e:
            self.error_occurred.emit(url, str(e))

    async def load_images(self):
        if not self.urls:
            return
        first_url = self.urls[0]
        async with aiohttp.ClientSession() as session:
            await self.fetch_one_image(session, first_url, 0)

            tasks = [
                self.fetch_with_semaphore(session, self.urls[idx], idx)
                for idx in range(1, len(self.urls))
            ]
            await asyncio.gather(*tasks)

    async def fetch_with_semaphore(self, session, url, index):
        """Fetch an image with a semaphore to limit parallel requests."""
        async with self.semaphore:
            await self.fetch_one_image(session, url, index)

    def stop(self):
        """Stop the loader"""
        self.running = False
        if self.loop and self.loop.is_running():
            for task in asyncio.all_tasks(self.loop):
                task.cancel()
            self.loop.call_soon_threadsafe(self.loop.stop)

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.load_images())
        except asyncio.CancelledError as e:
            self.logger.warning(f"Cancelled {str(e)}")  # Handle cancellation gracefully
        except RuntimeError as e:
            self.logger.warning(f"Runtime {str(e)}")  # Handle cancellation gracefully
        finally:
            self.loop.close()


class LocalImageLoader(QThread):
    """Thread to open images locally in batches"""

    image_loaded = pyqtSignal(bytes)

    def __init__(self, image_paths: list, image_list: list):
        # self.condition = QWaitCondition()
        self.mutex = QMutex()
        super().__init__()
        self.paths = image_paths
        self.index = 0
        # self.background_load_num = min(background_load_num, len(image_paths))
        self.image_list = image_list

    def run(self):
        with open(self.paths[0], "rb") as f:
            self.image_list[0] = f.read()
        self.image_loaded.emit(self.image_list[0])
        self.mutex.lock()
        for idx in range(1, len(self.paths)):

            with open(self.paths[idx], "rb") as f:
                self.image_list[idx] = f.read()
        # self.condition.wait(self.mutex)
        self.mutex.unlock()

    def wake_up(self):
        self.mutex.lock()
        # self.condition.wakeOne()
        self.mutex.unlock()
