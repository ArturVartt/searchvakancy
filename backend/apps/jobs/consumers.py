"""
WebSocket-consumer для real-time уведомлений о вакансиях.

Клиент подключается к ws://.../ws/jobs/ и получает сообщения вида:
    {"type": "new_job", "data": {...}}
    {"type": "job_updated", "data": {...}}
    {"type": "job_removed", "data": {"id": 123}}

Отправка событий из Celery-тасков (Phase 2) делается через
`broadcast_job_event()` ниже — она рассылает всем подключённым клиентам
через group "jobs".
"""
import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer

GROUP_NAME = "jobs"


class JobConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add(GROUP_NAME, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(GROUP_NAME, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Клиент ничего не отправляет — канал только для чтения (broadcast).
        # Отвечаем на ping/pong, чтобы соединение не считалось мёртвым.
        if text_data == "ping":
            await self.send(text_data="pong")

    # --- обработчики групповых событий (event["type"] == имя метода) -----

    async def job_new(self, event):
        await self.send(text_data=json.dumps({"type": "new_job", "data": event["data"]}))

    async def job_updated(self, event):
        await self.send(text_data=json.dumps({"type": "job_updated", "data": event["data"]}))

    async def job_removed(self, event):
        await self.send(text_data=json.dumps({"type": "job_removed", "data": event["data"]}))


def broadcast_job_event(event_type: str, data: dict) -> None:
    """
    Синхронный хелпер для вызова из Celery-тасков / сигналов.

    event_type: "new" | "updated" | "removed"
    """
    method_by_event = {
        "new": "job_new",
        "updated": "job_updated",
        "removed": "job_removed",
    }
    method = method_by_event.get(event_type)
    if method is None:
        raise ValueError(f"Unknown job event type: {event_type}")

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        GROUP_NAME,
        {"type": method, "data": data},
    )
