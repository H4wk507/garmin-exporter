import keyring
from keyring.errors import PasswordDeleteError

KEYRING_SERVICE = "garmin-exporter"
KEYRING_SESSION = "session"


def load_session() -> str | None:
    return keyring.get_password(KEYRING_SERVICE, KEYRING_SESSION)


def save_session(token: str) -> None:
    keyring.set_password(KEYRING_SERVICE, KEYRING_SESSION, token)


def _delete(user: str) -> None:
    try:
        keyring.delete_password(KEYRING_SERVICE, user)
    except PasswordDeleteError:
        pass


def delete_session() -> None:
    _delete(KEYRING_SESSION)
