"""Domain errors. Repositories and services raise these; main.py turns them into JSON responses,
so only the HTTP layer ever has to know about status codes."""


class AppError(Exception):
    status_code = 400

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class BadRequest(AppError):
    status_code = 400


class NotFound(AppError):
    status_code = 404


class Conflict(AppError):
    status_code = 409


class ServiceUnavailable(AppError):
    status_code = 503


class PayloadTooLarge(AppError):
    status_code = 413


class UnsupportedMediaType(AppError):
    status_code = 415
