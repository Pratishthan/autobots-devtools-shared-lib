# ABOUTME: End-to-end tests for the UI formatting pipeline.
# ABOUTME: Validates the full re-export chain from autobots_devtools_shared_lib.dynagent through bro_chat.

import pytest

from tests.conftest import requires_google_api


@requires_google_api
@pytest.mark.parametrize(
    "output_type,sample_data",
    [
        (
            "features",
            {
                "features": [
                    {
                        "name": "Login",
                        "description": "User auth",
                        "category": "core",
                        "priority": "must_have",
                    }
                ]
            },
        ),
        (
            "preface",
            {
                "about_this_guide": "A guide.",
                "audience": ["Devs"],
            },
        ),
        (
            "getting_started",
            {
                "overview": "Overview text.",
                "vision": "Vision text.",
                "success_metrics": ["Metric A"],
            },
        ),
        (
            "entity",
            {
                "name": "Order",
                "description": "An order.",
                "attributes": [{"name": "id", "type": "uuid"}],
            },
        ),
    ],
)
def test_e2e_formatting_pipeline(output_type: str, sample_data: dict):
    """Each known output_type produces non-empty markdown."""
    from bro_chat.utils.formatting import format_structured_output

    result = format_structured_output(sample_data, output_type=output_type)

    assert isinstance(result, str)
    assert len(result) > 0
