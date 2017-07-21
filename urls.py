# *************** DISCLAIMER **************
# This is the urls file of the project rather than the app
# Do not copy it directly
# *****************************************

from django.conf.urls import include, url
from django.contrib import admin
from upload_download import views

urlpatterns = [
    url(r'^admin/', include(admin.site.urls)),
    url(r'^$', views.index, name='index'),
    url(r'^list_folder/$', views.show_folder_contents, name='show_folder_contents'),
    url(r'^download_file/(?P<file_id>.+)/$', views.download_file, name='download_file'),
    url(r'^upload_file/(?P<folder_id>.+)/$', views.upload_file, name='upload_file'),
    url(r'^oauth2callback/$', views.oauth2callback, name='oauth2callback'),
]
