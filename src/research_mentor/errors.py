"""Exception hierarchy for Research Mentor Core."""


class ResearchMentorError(Exception):
    """Research Mentor Core 基础异常。"""


class DuplicateSessionError(ResearchMentorError):
    """会话重复异常。"""


class IllegalTransitionError(ResearchMentorError):
    """非法状态转换异常。"""


class InvariantViolationError(ResearchMentorError):
    """不变量违反异常。"""


class PortExecutionError(ResearchMentorError):
    """端口执行异常。"""


class SessionNotFoundError(ResearchMentorError):
    """会话不存在异常。"""


class ValidationSelectionError(ResearchMentorError):
    """验证候选选择不满足队列约束。"""
