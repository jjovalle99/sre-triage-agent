import os

_DEFAULT = "On-Call Engineer"


def get_oncall_engineer() -> str:
    return os.environ.get("ON_CALL_ENGINEER", _DEFAULT)
