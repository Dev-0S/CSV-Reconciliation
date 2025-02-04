from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('generate_csv/', views.generate_csv_view, name='generate_csv'),
]