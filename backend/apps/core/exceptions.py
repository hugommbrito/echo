"""Uniform API errors: `{ "detail": str, "code": str, ...extra }`."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class ConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict."
    default_code = "conflict"

    def __init__(self, detail=None, code=None, extra: dict | None = None):
        super().__init__(detail, code)
        self.extra = extra or {}


class ServiceUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Service temporarily unavailable."
    default_code = "service_unavailable"


def _first_code(codes) -> str:
    if isinstance(codes, str):
        return codes
    if isinstance(codes, dict):
        for value in codes.values():
            return _first_code(value)
    if isinstance(codes, list | tuple):
        for value in codes:
            return _first_code(value)
    return "error"


def exception_handler(exc, context):
    if isinstance(exc, Http404):
        return Response({"detail": "Not found.", "code": "not_found"}, status=404)
    if isinstance(exc, PermissionDenied):
        return Response({"detail": "Permission denied.", "code": "permission_denied"}, status=403)

    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, ValidationError):
        response.data = {
            "detail": "Validation error.",
            "code": "validation_error",
            "errors": exc.detail,
        }
        return response

    if isinstance(exc, APIException):
        detail = exc.detail
        if isinstance(detail, dict) and "detail" in detail:
            payload = dict(detail)
        else:
            payload = {"detail": str(detail)}
        payload.setdefault("code", _first_code(exc.get_codes()))
        if isinstance(exc, ConflictError):
            payload.update(exc.extra)
        response.data = payload
    return response
