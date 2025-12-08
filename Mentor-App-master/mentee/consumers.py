import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.serializers.json import DjangoJSONEncoder
from .models import Reply, Reaction, ReplySeen
from django.contrib.auth import get_user_model

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conv_id = self.scope['url_route']['kwargs']['conv_id']
        self.room_group_name = f"conversation_{self.conv_id}"

        # join group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        user = self.scope['user']
        # broadcast presence joined
        await self.channel_layer.group_send(self.room_group_name, {
            "type": "presence",
            "user_id": user.id,
            "username": getattr(user, "username", ""),
            "joined": True,
        })

    async def disconnect(self, close_code):
        # leave group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        user = self.scope['user']
        await self.channel_layer.group_send(self.room_group_name, {
            "type": "presence",
            "user_id": user.id,
            "username": getattr(user, "username", ""),
            "joined": False,
        })

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            data = json.loads(text_data)
        except:
            return

        action = data.get("action")
        user = self.scope.get("user")

        if action == "typing":
            # broadcast typing state
            await self.channel_layer.group_send(self.room_group_name, {
                "type": "typing",
                "user_id": user.id,
                "username": getattr(user, "username", ""),
                "typing": data.get("typing", False),
            })

        elif action == "seen":
            reply_id = data.get("reply_id")
            if reply_id:
                # mark seen in DB and notify group
                saved = await self.mark_seen(reply_id, user.id)
                if saved:
                    await self.channel_layer.group_send(self.room_group_name, {
                        "type": "seen_event",
                        "reply_id": reply_id,
                        "user_id": user.id,
                    })

        elif action == "reaction":
            reply_id = data.get("reply_id")
            emoji = data.get("emoji")
            if reply_id and emoji:
                reaction = await self.add_reaction(reply_id, user.id, emoji)
                if reaction:
                    await self.channel_layer.group_send(self.room_group_name, {
                        "type": "reaction_event",
                        "reply_id": reply_id,
                        "user_id": user.id,
                        "emoji": emoji,
                    })

        # Note: we DON'T create messages from WS client in this implementation.
        # Message creation happens via HTTP upload view which broadcasts to group,
        # avoiding race issues with file uploads and returned DB ids.

    # Group event handlers (these are invoked via group_send)
    async def typing(self, event):
        await self.send_json({
            "action": "typing",
            "user_id": event["user_id"],
            "username": event["username"],
            "typing": event["typing"],
        })

    async def new_message(self, event):
        # event['message'] is serializable payload from server
        await self.send_json({
            "action": "new_message",
            "message": event["message"]
        })

    async def seen_event(self, event):
        await self.send_json({
            "action": "seen_event",
            "reply_id": event["reply_id"],
            "user_id": event["user_id"]
        })

    async def reaction_event(self, event):
        await self.send_json({
            "action": "reaction",
            "reply_id": event["reply_id"],
            "user_id": event["user_id"],
            "emoji": event["emoji"]
        })

    async def presence(self, event):
        await self.send_json({
            "action": "presence",
            "user_id": event["user_id"],
            "username": event["username"],
            "joined": event["joined"],
        })

    async def edited_message(self, event):
        await self.send_json({
            "action": "edited_message",
            "message": event["message"]
        })

    async def deleted_message(self, event):
        await self.send_json({
            "action": "deleted_message",
            "message": event["message"]
        })

    # DB helpers
    @database_sync_to_async
    def reply_to_json(self, reply):
        file_url = None
        try:
            if reply.file and hasattr(reply.file, 'url'):
                file_url = reply.file.url
        except:
            file_url = None

        # reactions and seen count - adapt if relation names differ
        reactions = []
        try:
            for r in reply.reaction_set.all():
                reactions.append({"user_id": r.user_id, "emoji": r.emoji})
        except:
            reactions = []

        seen_count = reply.seen_by.count() if hasattr(reply, 'seen_by') else 0

        return {
            "id": reply.id,
            "sender_id": reply.sender.id if reply.sender else None,
            "sender_username": getattr(reply.sender, "username", ""),
            "text": reply.reply,
            "file_url": file_url,
            "replied_at": (reply.replied_at.isoformat() if reply.replied_at else None),
            "reactions": reactions,
            "seen_count": seen_count,
        }

    @database_sync_to_async
    def mark_seen(self, reply_id, user_id):
        try:
            reply = Reply.objects.get(pk=reply_id)
            user = User.objects.get(pk=user_id)
            ReplySeen.objects.get_or_create(reply=reply, user=user)
            return True
        except Exception:
            return False

    @database_sync_to_async
    def add_reaction(self, reply_id, user_id, emoji):
        try:
            reply = Reply.objects.get(pk=reply_id)
            user = User.objects.get(pk=user_id)
            reaction, created = Reaction.objects.update_or_create(reply=reply, user=user, defaults={"emoji": emoji})
            return reaction
        except Exception:
            return None

    # convenience: send json wrapper
    async def send_json(self, payload):
        await self.send(text_data=json.dumps(payload, cls=DjangoJSONEncoder))
