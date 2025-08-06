from typing import Literal, Optional, TypedDict

StatusLiteral = Literal["queued", "processing", "completed", "failed"]


class TranscriptionStatus(TypedDict, total=False):
    """
    Shape returned by GET /transcribe/status/{job_id}
    (Fields are optional to tolerate server-side evolution.)
    """
    job_id: str
    status: StatusLiteral
    transcript: Optional[str]
    error_code: Optional[str]
    error_message: Optional[str]
    created_at: str
    completed_at: Optional[str]
