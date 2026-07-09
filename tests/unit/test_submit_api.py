"""Tests for tracker submit HTTP client."""

from unittest.mock import MagicMock

import pytest

from cngx.cli.submit_cmd import build_submit_payload, post_submit_payload, validate_submit_payload
from tests.unit.test_submit_privacy import _sample_fingerprint


class TestSubmitApi:
    def test_post_success(self):
        fp = _sample_fingerprint()
        payload = build_submit_payload(fp, baseline_label="b", drift_score=0.2)

        response = MagicMock()
        response.status_code = 201
        response.json.return_value = {"ok": True, "record_id": payload["record_id"]}

        client = MagicMock()
        client.post.return_value = response

        record_id = post_submit_payload(
            payload,
            endpoint="https://example.test/submit",
            client=client,
        )
        assert record_id == payload["record_id"]
        client.post.assert_called_once()
        sent = client.post.call_args.kwargs["json"]
        validate_submit_payload(sent)

    def test_post_rejects_bad_status(self):
        fp = _sample_fingerprint()
        payload = build_submit_payload(fp, baseline_label="b", drift_score=0.2)

        response = MagicMock()
        response.status_code = 400
        response.text = '{"error":"bad"}'
        response.json.return_value = {"error": "bad"}

        client = MagicMock()
        client.post.return_value = response

        with pytest.raises(RuntimeError, match="Submit failed"):
            post_submit_payload(payload, endpoint="https://example.test/submit", client=client)

    def test_placeholder_endpoint_blocked(self):
        fp = _sample_fingerprint()
        payload = build_submit_payload(fp, baseline_label="b", drift_score=0.2)
        with pytest.raises(RuntimeError, match="not configured"):
            post_submit_payload(payload, endpoint="https://PLACEHOLDER/submit")
