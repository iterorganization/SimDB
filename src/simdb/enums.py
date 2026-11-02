from enum import Enum


class IngestionStatus(str, Enum):
    QUEUED = "QUEUED"
    COPYING = "COPYING"
    COPIED = "COPIED"
    # Retained for database migration compatibility; v1.3 runs validation
    # decoupled after COMPLETED:
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    COMPLETED = "COMPLETED"

    COPY_FAILED = "COPY_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"

    def is_terminal(self) -> bool:
        """Whether the ingestion file transfer pipeline has finished
        (COMPLETED, COPY_FAILED, or legacy VALIDATION_FAILED).

        Note: When ``validation.auto_validate`` is enabled, background validation
        runs as an asynchronous follow-up task after ingestion is COMPLETED.
        """
        return self in (
            IngestionStatus.COMPLETED,
            IngestionStatus.COPY_FAILED,
            IngestionStatus.VALIDATION_FAILED,
        )
