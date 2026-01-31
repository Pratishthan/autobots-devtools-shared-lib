# ABOUTME: SectionStatus enum representing vision document section states.
# ABOUTME: Defines lifecycle from not_started to complete with intermediate states.

from enum import Enum


class SectionStatus(Enum):
    """Status of a section in a vision document.

    Lifecycle: not_started -> in_progress -> draft/needs_detail -> complete
    """

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    NEEDS_DETAIL = "needs_detail"
    DRAFT = "draft"
    COMPLETE = "complete"
