"""Oracle Object Storage rejects aws-chunked uploads, so botocore must not send them.

Without `request_checksum_calculation="when_required"` botocore adds a CRC32 checksum on its own
and streams the body as `Content-Encoding: aws-chunked`; Oracle answers `NotImplemented: AWS
chunked encoding not supported` and the upload endpoint turns that into a 500.
"""

import io

from django.conf import settings
from storages.backends.s3 import S3Storage


class Intercepted(Exception):
    """Raised from the `before-send` hook: the request is inspected, never sent."""

    def __init__(self, headers):
        self.headers = headers


def _decode(value) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


def put_object_headers(**config_overrides) -> dict[str, str]:
    """The headers boto3 would send for a PutObject, captured just before the network call."""
    config = settings.S3_CLIENT_CONFIG
    if config_overrides:
        config = config.merge(type(config)(**config_overrides))
    storage = S3Storage(
        bucket_name="echo-audio",
        endpoint_url="https://ns.compat.objectstorage.sa-saopaulo-1.oraclecloud.com",
        access_key="access-key",
        secret_key="secret-key",
        region_name="sa-saopaulo-1",
        client_config=config,
        default_acl=None,
        file_overwrite=False,
    )

    def before_send(request, **kwargs):
        raise Intercepted({k.lower(): _decode(v) for k, v in request.headers.items()})

    storage.connection.meta.client.meta.events.register("before-send.s3.PutObject", before_send)
    try:
        storage._save("users/u1/attempts/a1.webm", io.BytesIO(b"fake-webm-bytes"))
    except BaseException as exc:  # s3transfer re-raises the failure from inside its future
        while exc is not None:
            if isinstance(exc, Intercepted):
                return exc.headers
            exc = exc.__cause__ or exc.__context__
        raise
    raise AssertionError("the request was not intercepted")


def test_upload_is_a_plain_body():
    headers = put_object_headers()
    assert "aws-chunked" not in headers.get("content-encoding", "")
    assert headers.get("transfer-encoding") != "chunked"
    assert "x-amz-trailer" not in headers
    assert headers["content-length"] == "15"


def test_botocore_default_would_break_oracle():
    """Pins the reason the override exists: the default is what Oracle refuses."""
    headers = put_object_headers(request_checksum_calculation="when_supported")
    assert headers["content-encoding"] == "aws-chunked"


def test_client_config_keeps_path_addressing_and_sigv4():
    """The override replaces the config django-storages builds, so it must carry these too."""
    assert settings.S3_CLIENT_CONFIG.s3["addressing_style"] == "path"
    assert settings.S3_CLIENT_CONFIG.signature_version == "s3v4"
