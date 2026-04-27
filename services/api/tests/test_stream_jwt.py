from __future__ import annotations

from uuid import uuid4

import pytest

from flow.infrastructure.auth.jwt_utils import (
    create_access_token,
    create_stream_token,
    decode_stream_token,
)


def test_stream_token_roundtrip() -> None:
    secret = "test-secret-at-least-32-chars-long!!"
    uid = uuid4()
    eid = uuid4()
    tok = create_stream_token(secret=secret, sub=uid, execution_id=eid, ttl_seconds=60)
    u2, e2 = decode_stream_token(secret, tok)
    assert u2 == uid
    assert e2 == eid


def test_access_token_rejected_for_stream_decode() -> None:
    secret = "test-secret-at-least-32-chars-long!!"
    access = create_access_token(secret=secret, sub=uuid4())
    with pytest.raises(ValueError, match="wrong token type"):
        decode_stream_token(secret, access)


def test_stream_token_bad_secret() -> None:
    tok = create_stream_token(secret="a" * 32, sub=uuid4(), execution_id=uuid4())
    with pytest.raises(ValueError):
        decode_stream_token("b" * 32, tok)
