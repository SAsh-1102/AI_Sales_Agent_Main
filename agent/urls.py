from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),  # root of /agent/
    path("chat/", views.chat_api, name="chat_api"),
    path("voice/", views.voice_api, name="voice_api"),
     path('webrtc/agent/', views.webrtc_agent, name='webrtc_agent'),
    path('webrtc/customer/', views.webrtc_customer, name='webrtc_customer'),
    path('api/webrtc/signal/', views.webrtc_signal, name='webrtc_signal'),
    path('api/webrtc/poll/', views.webrtc_poll, name='webrtc_poll'),
    path('agent/api/webrtc/process-audio/', views.webrtc_process_audio, name='webrtc_process_audio'),

]
