from enum import StrEnum


class TaskStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    SUBMITTED = "submitted"
    CHANGES_REQUESTED = "changes_requested"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# (source, command) -> destination. This also drives the architecture diagram.
TRANSITIONS: dict[tuple[TaskStatus, str], TaskStatus] = {
    (TaskStatus.NOT_STARTED, "start"): TaskStatus.IN_PROGRESS,
    (TaskStatus.IN_PROGRESS, "pause"): TaskStatus.PAUSED,
    (TaskStatus.PAUSED, "resume"): TaskStatus.IN_PROGRESS,
    (TaskStatus.IN_PROGRESS, "submit"): TaskStatus.SUBMITTED,
    (TaskStatus.SUBMITTED, "request_changes"): TaskStatus.CHANGES_REQUESTED,
    (TaskStatus.CHANGES_REQUESTED, "resume"): TaskStatus.IN_PROGRESS,
    (TaskStatus.SUBMITTED, "pass"): TaskStatus.COMPLETED,
    **{
        (status, "cancel"): TaskStatus.CANCELLED
        for status in TaskStatus
        if status not in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}
    },
}
