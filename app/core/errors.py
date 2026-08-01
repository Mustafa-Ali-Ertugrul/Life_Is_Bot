class AppError(Exception):
    """Uygulama seviyesinde beklenen hata."""


class NotFoundError(AppError):
    """Kayıt bulunamadı."""


class PermissionDeniedError(AppError):
    """Kullanıcı bu işlemi yapamaz."""


class InvalidStateError(AppError):
    """Kayıt bu işlem için uygun durumda değil."""


__all__ = [
    "AppError",
    "InvalidStateError",
    "NotFoundError",
    "PermissionDeniedError",
]
