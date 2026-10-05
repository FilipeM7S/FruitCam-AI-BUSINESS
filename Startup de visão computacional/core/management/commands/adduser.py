import getpass
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create a FruitCam user. Password from $FRUITCAM_NEW_PASSWORD or an interactive prompt."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, username, **options):
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise CommandError(f"user {username!r} already exists")
        password = os.environ.get("FRUITCAM_NEW_PASSWORD") or getpass.getpass("Password: ")
        try:
            validate_password(password, User(username=username))
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages))
        User.objects.create_user(username, password=password)
        self.stdout.write(f"created user {username}")
