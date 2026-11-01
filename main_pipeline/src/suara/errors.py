"""Public error construction; messages must not contain private input details."""
from typing import Literal

from suara.contracts import ErrorCode, ErrorInfo, PipelineError

Stage = Literal["configuration", "preprocessing", "pitch", "timbre", "profile", "recommendation"]


def failure(code: ErrorCode, stage: Stage, message: str) -> PipelineError:
    return PipelineError(ErrorInfo(code=code, stage=stage, message=message))


def validate_top_k(top_k: int) -> None:
    if type(top_k) is not int or not 1 <= top_k <= 5:
        raise failure("invalid_configuration", "configuration", "top_k must be an integer from 1 to 5.")
