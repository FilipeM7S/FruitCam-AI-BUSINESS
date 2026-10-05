import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fruitcam.settings")
application = get_wsgi_application()

from core.inference import get_model

get_model()
