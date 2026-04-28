# ABOUTME: Loads jira.yaml from the same config directory as agents.yaml.
# ABOUTME: Returns None silently when jira.yaml is absent (Jira integration is opt-in).
# ABOUTME: Owns the JiraConfig singleton — get_jira_config() is the shared access point.

from __future__ import annotations

import yaml

from autobots_devtools_shared_lib.common.config.jira_config import JIRA_CONFIG_FILENAME, JiraConfig
from autobots_devtools_shared_lib.common.observability.logging_utils import get_logger

logger = get_logger(__name__)

_config: JiraConfig | None = None
_config_loaded: bool = False


def set_jira_config(config: JiraConfig | None) -> None:
    """Explicitly set the Jira config singleton (useful for tests or custom injection)."""
    global _config, _config_loaded
    _config = config
    _config_loaded = True


def get_jira_config() -> JiraConfig | None:
    """Return the cached JiraConfig, loading from disk on the first call.

    Jira config is optional — returns None when jira.yaml is absent.
    The result (including None) is cached after the first call so the filesystem
    is only read once regardless of outcome.
    """
    global _config, _config_loaded
    if not _config_loaded:
        set_jira_config(_load_jira_config())
    return _config


def _load_jira_config() -> JiraConfig | None:
    from autobots_devtools_shared_lib.dynagent.agents.agent_config_utils import get_config_dir

    config_dir = get_config_dir()
    jira_path = config_dir / JIRA_CONFIG_FILENAME

    if not jira_path.exists():
        logger.debug(
            "No jira.yaml found at %s; Jira tools will not be registered", jira_path
        )
        return None

    logger.info("Loading Jira config from %s", jira_path)
    with open(jira_path) as f:  # noqa: PTH123
        raw = yaml.safe_load(f)

    config = JiraConfig.model_validate(raw["jira_config"])
    logger.info("Loaded Jira config: base_url=%s", config.base_url)
    return config
