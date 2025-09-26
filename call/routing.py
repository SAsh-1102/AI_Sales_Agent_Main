# from django.urls import re_path
# from . import consumers

# websocket_urlpatterns = [
#     re_path(r'ws/call/$', consumers.CallConsumer.as_asgi()), # type: ignore
# ]
# call/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/call/(?P<username>\w+)/$', consumers.CallConsumer.as_asgi()),
]

