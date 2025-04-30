from django.urls import path
from myapp import views
urlpatterns = [
    path('upload', views.upload_bill, name='upload'),
    path('login', views.login, name='login'),
    path('createuser', views.create_user, name='create_user'),
    path('bill_details', views.bill_details, name='bill_details'),
    path('change_pass', views.change_pass, name='change_pass'),
    path('typeofbills', views.typeofbills_master, name='typeofbills'),
    path('modeofbills', views.modeofbills_master, name='modeofbills'),
    path('rolemaster', views.role_master, name='role_master'),
    path('usermaster', views.user_master, name='user_master'),
    path('companyname', views.companyname_master, name='companyname'),
    path('last_five_bill_details', views.last_five_bill_details, name='last_five_bill_details'),
    path('dashboard_count', views.dashboard_count, name='dashboard_count'),
    path('updateprofile', views.update_profile, name='update_profile'),
]