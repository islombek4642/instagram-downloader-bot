import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DownloadTask:
    """Yuklash vazifasi."""
    chat_id: int
    instagram_url: str
    user_message_id: int
    created_at: datetime
    attempts: int = 0
    max_attempts: int = 3


class QueueManager:
    """Yuklash navbati boshqaruvchisi."""
    
    def __init__(self, max_concurrent: int = 3, max_queue_size: int = 100):
        self.max_concurrent = max_concurrent
        self.max_queue_size = max_queue_size
        
        self._queue: asyncio.Queue[DownloadTask] = asyncio.Queue(maxsize=max_queue_size)
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._user_queues: Dict[int, List[DownloadTask]] = {}  # Per-user queue tracking
        
        self._worker_tasks: List[asyncio.Task] = []
        self._shutdown = False
    
    async def start(self) -> None:
        """Queue worker'larini ishga tushirish."""
        logger.info(f"Starting queue manager with {self.max_concurrent} workers")
        
        for i in range(self.max_concurrent):
            worker_task = asyncio.create_task(self._worker(f"worker-{i}"))
            self._worker_tasks.append(worker_task)
    
    async def stop(self) -> None:
        """Queue manager'ni to'xtatish."""
        logger.info("Stopping queue manager...")
        self._shutdown = True
        
        # Worker'larni kutish
        for task in self._worker_tasks:
            task.cancel()
        
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        
        # Faol vazifalarni bekor qilish
        for task in self._active_tasks.values():
            task.cancel()
        
        if self._active_tasks:
            await asyncio.gather(*self._active_tasks.values(), return_exceptions=True)
    
    async def add_task(self, task: DownloadTask) -> bool:
        """Navbatga vazifa qo'shish."""
        try:
            # User uchun maksimal vazifalar soni tekshirish
            user_tasks = self._user_queues.get(task.chat_id, [])
            if len(user_tasks) >= 5:  # Har bir user uchun max 5 ta vazifa
                logger.warning(f"Too many tasks for user {task.chat_id}")
                return False
            
            # Navbat to'lib ketgan bo'lsa
            if self._queue.full():
                logger.warning("Queue is full, rejecting new task")
                return False
            
            # Vazifani navbatga qo'yish
            await self._queue.put(task)
            
            # User tracking
            if task.chat_id not in self._user_queues:
                self._user_queues[task.chat_id] = []
            self._user_queues[task.chat_id].append(task)
            
            logger.info(f"Added task to queue: {task.instagram_url} for user {task.chat_id}")
            return True
            
        except asyncio.QueueFull:
            logger.warning("Queue is full")
            return False
    
    async def _worker(self, worker_name: str) -> None:
        """Queue worker - vazifalarni bajarish."""
        logger.info(f"Started worker: {worker_name}")
        
        while not self._shutdown:
            try:
                # Vazifani navbatdan olish (5 sekund kutish)
                task = await asyncio.wait_for(self._queue.get(), timeout=5.0)
                
                # Vazifani bajarish
                task_id = f"{task.chat_id}_{task.user_message_id}"
                
                try:
                    logger.info(f"[{worker_name}] Processing task: {task.instagram_url}")
                    
                    # Vazifani boshqa joyda bajarish uchun signal yuborish
                    # Bu yerda faqat logging qilamiz, aslida ishlov download handler da bo'ladi
                    await self._process_download_task(task)
                    
                    logger.info(f"[{worker_name}] Completed task: {task.instagram_url}")
                    
                except Exception as exc:
                    logger.error(f"[{worker_name}] Task failed: {task.instagram_url}, error: {str(exc)}")
                    
                    # Qayta urinish
                    task.attempts += 1
                    if task.attempts < task.max_attempts:
                        logger.info(f"Retrying task {task.instagram_url}, attempt {task.attempts}")
                        await asyncio.sleep(2)  # Qisqa kutish
                        await self._queue.put(task)
                    else:
                        logger.error(f"Task failed permanently: {task.instagram_url}")
                
                finally:
                    # User tracking dan o'chirish
                    if task.chat_id in self._user_queues:
                        try:
                            self._user_queues[task.chat_id].remove(task)
                            if not self._user_queues[task.chat_id]:
                                del self._user_queues[task.chat_id]
                        except ValueError:
                            pass  # Task allaqachon o'chirilgan
                    
                    # Active tasks dan o'chirish
                    self._active_tasks.pop(task_id, None)
                    
                    # Queue task done signali
                    self._queue.task_done()
                    
            except asyncio.TimeoutError:
                # Queue bo'sh - davom etish
                continue
            except Exception as exc:
                logger.error(f"Worker {worker_name} error: {str(exc)}")
                await asyncio.sleep(1)
        
        logger.info(f"Worker {worker_name} stopped")
    
    async def _process_download_task(self, task: DownloadTask) -> None:
        """Yuklash vazifasini bajarish - bu yerda asliy download logikasi bo'ladi."""
        # Bu metodda asosiy download handler chaqiriladi
        # Hozircha placeholder
        await asyncio.sleep(1)  # Simulate work
    
    def get_stats(self) -> Dict[str, int]:
        """Queue statistikasi."""
        return {
            "queue_size": self._queue.qsize(),
            "max_queue_size": self.max_queue_size,
            "active_tasks": len(self._active_tasks),
            "max_concurrent": self.max_concurrent,
            "users_in_queue": len(self._user_queues),
        }


# Global queue manager instance
_queue_manager: Optional[QueueManager] = None


async def get_queue_manager() -> QueueManager:
    """Global queue manager olish."""
    global _queue_manager
    
    if _queue_manager is None:
        _queue_manager = QueueManager(max_concurrent=3, max_queue_size=100)
        await _queue_manager.start()
    
    return _queue_manager


async def shutdown_queue_manager() -> None:
    """Queue manager'ni o'chirish."""
    global _queue_manager
    
    if _queue_manager is not None:
        await _queue_manager.stop()
        _queue_manager = None
