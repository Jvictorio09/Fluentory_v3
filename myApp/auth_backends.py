"""Custom authentication backends for Fluentory."""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameModelBackend(ModelBackend):
    """Authenticate using either a username or an email address.

    The login form keeps the field name ``username`` for compatibility, but the
    submitted value may be either the account's username or its email. Matching
    is case-insensitive for both.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        # Django's LoginView/ModelBackend may pass the identifier as USERNAME_FIELD.
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None

        identifier = username.strip()
        try:
            # Match on username OR email, case-insensitively.
            user = UserModel.objects.get(
                Q(username__iexact=identifier) | Q(email__iexact=identifier)
            )
        except UserModel.DoesNotExist:
            # Run the default hasher once to mitigate timing attacks that could
            # reveal whether an account exists.
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            # Ambiguous (e.g. a username equals another account's email). Prefer
            # an exact username match, then the most recently joined account.
            user = (
                UserModel.objects.filter(username__iexact=identifier).first()
                or UserModel.objects.filter(email__iexact=identifier)
                .order_by('-date_joined')
                .first()
            )
            if user is None:
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
