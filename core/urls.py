from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views import list_bins

urlpatterns = [
    path('', views.home_view, name='home_view'),
    path('register/', views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(redirect_authenticated_user=True, template_name='core/auth/login.html', next_page='inventory_view'), name='login'),
    path('inventory/', views.inventory_view, name='inventory_view'),
    path('expand_inventory/', views.expand_inventory_view, name='expand_inventory'),
    path('create_bin/', views.create_bin_view, name='create_bin'),
    path('add_items_to_bin/', views.add_items_to_bin_view, name='add_items_to_bin'),
    path('bins/', list_bins, name='list_bins'),
    path('bin/<int:bin_id>/', views.bin_detail, name='bin_detail'),
    path('item/<int:item_id>/', views.item_detail, name='item_detail'),
]