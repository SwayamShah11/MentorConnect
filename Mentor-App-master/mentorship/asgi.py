import os
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
import mentee.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mentorship.settings')

# IMPORTANT: Do NOT call django.setup() manually in ASGI!
django_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            mentee.routing.websocket_urlpatterns
        )
    ),
})
