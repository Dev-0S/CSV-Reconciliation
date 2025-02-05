from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('generate_csv/', views.generate_csv_view, name='generate_csv'),
    path('crypto_pnl/', views.crypto_pnl_view, name='crypto_pnl'),
    path('generate_dummy_trades/', views.generate_dummy_trades_csv, name='generate_dummy_trades'),

]