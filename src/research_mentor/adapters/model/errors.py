"""Provider-specific structured model errors."""

from research_mentor.errors import ResearchMentorError


class ModelTemporarilyUnavailable(ResearchMentorError):
    """模型 provider 暂时不可用，可由 application 层重试。"""


class ModelProviderRejected(ResearchMentorError):
    """模型 provider 拒绝了不可重试的请求。"""
