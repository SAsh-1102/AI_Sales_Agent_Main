from django.contrib import admin
from django.urls import path, include
from agent.views import index  # for homepage
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path("admin/", admin.site.urls),       
    path("agent/", include("agent.urls")),   
    path("call/", include("call.urls")),      
    path("", index, name="home"),          
 ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


 