# ABOUTME: Loads jenkins.yaml from the same config directory as agents.yaml.
# ABOUTME: Returns None silently when jenkins.yaml is absent (feature is opt-in).
# ABOUTME: Owns the JenkinsConfig singleton — get_jenkins_config() is the shared access point.

from __future__ import annotations

import yaml

from autobots_devtools_shared_lib.common.config.jenkins_config import JenkinsConfig
from autobots_devtools_shared_lib.common.config.jenkins_constants import JENKINS_CONFIG_FILENAME
from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger

logger = get_logger(__name__)

_config: JenkinsConfig | None = None
_config_loaded: bool = False


def set_jenkins_config(config: JenkinsConfig | None) -> None:
    """Explicitly set the Jenkins config singleton (useful for tests or custom injection)."""
    global _config, _config_loaded
    _config = config
    _config_loaded = True


def get_jenkins_config() -> JenkinsConfig | None:
    """Return the cached JenkinsConfig, loading from disk on the first call.

    Jenkins config is optional — returns None when jenkins.yaml is absent.
    The result (including None) is cached after the first call so the filesystem
    is only read once regardless of outcome. Subsequent calls return immediately.

    Raises:
        yaml.YAMLError: If the file contains invalid YAML (first call only).
        pydantic.ValidationError: If the YAML structure does not match the schema (first call only).
    """
    global _config, _config_loaded
    if not _config_loaded:
        set_jenkins_config(load_jenkins_config())
    return _config


def load_jenkins_config() -> JenkinsConfig | None:
    """Load and validate jenkins.yaml from the active config directory.

    Reads from the same directory as agents.yaml (controlled by
    DYNAGENT_CONFIG_ROOT_DIR). Returns None if jenkins.yaml is absent so
    callers do not need to handle the optional file specially.

    Prefer get_jenkins_config() over this function when a cached singleton
    is acceptable — load_jenkins_config() always reads from disk.

    Returns:
        Validated JenkinsConfig or None if the file does not exist.

    Raises:
        yaml.YAMLError: If the file contains invalid YAML.
        pydantic.ValidationError: If the YAML structure does not match the schema.
    """
    from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import get_config_dir

    config_dir = get_config_dir()
    jenkins_path = config_dir / JENKINS_CONFIG_FILENAME

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
