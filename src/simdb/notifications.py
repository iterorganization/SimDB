from enum import Enum


class Notification(Enum):
    VALIDATION = "validation"
    REVISION = "revision"
    OBSOLESCENCE = "obsolescence"
    ALL = "all"
