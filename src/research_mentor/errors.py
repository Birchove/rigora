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


class ConcurrencyConflict(ResearchMentorError):
    """持久化版本与调用方预期不一致。"""

    def __init__(self, resource_id: str, expected_version: int) -> None:
        self.resource_id = resource_id
        self.expected_version = expected_version
        super().__init__(
            f"Version conflict for {resource_id}: expected {expected_version}"
        )


class InvalidStorageIdentifier(ResearchMentorError):
    """文件存储标识符可能导致路径越界。"""


class DocumentParseFailed(ResearchMentorError):
    """上传文档无法转换为规范 Markdown。"""


class LiteratureSearchUnavailable(ResearchMentorError):
    """文献 provider 当前不可用或拒绝了请求。"""


class ModelOutputInvalid(ResearchMentorError):
    """模型返回内容不符合请求的 structured output schema。"""

    def __init__(self, errors: list[dict[str, object]]) -> None:
        self.errors = errors
        super().__init__("Structured model output is invalid")
