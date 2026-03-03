# ABOUTME: Loads jenkins.yaml from the same config directory as agents.yaml.
# ABOUTME: Returns None silently when jenkins.yaml is absent (feature is opt-in).

from __future__ import annotations

import yaml

from autobots_devtools_shared_lib.common.config.jenkins_config import JenkinsConfig
from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger

logger = get_logger(__name__)


def load_jenkins_config() -> JenkinsConfig | None:
    """Load and validate jenkins.yaml from the active config directory.

    Reads from the same directory as agents.yaml (controlled by
    DYNAGENT_CONFIG_ROOT_DIR). Returns None if jenkins.yaml is absent so
    callers do not need to handle the optional file specially.

    Returns:
        Validated JenkinsConfig or None if the file does not exist.

    Raises:
        yaml.YAMLError: If the file contains invalid YAML.
        pydantic.ValidationError: If the YAML structure does not match the schema.
    """
    from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import get_config_dir

    config_dir = get_config_dir()
    jenkins_path = config_dir / "jenkins.yaml"

    if not jenkins_path.exists():
        logger.debug(
            f"No jenkins.yaml found at {jenkins_path}; Jenkins tools will not be registered"
        )
        return None

    logger.info(f"Loading Jenkins config from {jenkins_path}")
    with open(jenkins_path) as f:  # noqa: PTH123
        raw = yaml.safe_load(f)

    config = JenkinsConfig.model_validate(raw["jenkins_config"])
    logger.info(
        f"Loaded Jenkins config with {len(config.pipelines)} pipeline(s): {list(config.pipelines)}"
    )
    return config
