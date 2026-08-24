"""Domain exceptions.

Every exception carries a stable `code` (product-spec-facing) and an HTTP
`status` the API layer maps 1:1 — see app/api/errors.py. Domain code never
imports FastAPI; it only raises these.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base for all domain-level failures. `details` is JSON-serialisable."""

    code: str = "DOMAIN_ERROR"
    status: int = 422

    def __init__(self, message: str, *, details: list[dict] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []


class ProjectNotFoundError(DomainError):
    code = "PROJECT_NOT_FOUND"
    status = 404


class TaskNotFoundError(DomainError):
    code = "TASK_NOT_FOUND"
    status = 422


class DuplicateTaskNameError(DomainError):
    code = "DUPLICATE_TASK_NAME"
    status = 422


class DependencyCycleError(DomainError):
    code = "DEPENDENCY_CYCLE"
    status = 422


class SelfDependencyError(DomainError):
    code = "SELF_DEPENDENCY"
    status = 422


class DependencyNotFoundError(DomainError):
    code = "DEPENDENCY_NOT_FOUND"
    status = 422


class DateConstraintViolationError(DomainError):
    code = "DATE_CONSTRAINT_VIOLATION"
    status = 422


class UnsupportedEffortGranularityError(DomainError):
    code = "UNSUPPORTED_EFFORT_GRANULARITY"
    status = 422


class InvalidClientRefError(DomainError):
    code = "INVALID_CLIENT_REF"
    status = 422


class UnresolvedClientRefError(DomainError):
    code = "UNRESOLVED_CLIENT_REF"
    status = 422


class RevisionConflictError(DomainError):
    code = "REVISION_CONFLICT"
    status = 409


class InvalidDurationError(DomainError):
    code = "INVALID_DURATION"
    status = 422


class DependencyAlreadyExistsError(DomainError):
    code = "DEPENDENCY_ALREADY_EXISTS"
    status = 422


class InvalidTaskFieldError(DomainError):
    code = "INVALID_TASK_FIELD"
    status = 422


class ChangeSetRejectedError(DomainError):
    """Wraps any of the above raised while applying a change set, so the API
    layer can return one HTTP 422 with the original error's code preserved."""

    code = "CHANGE_SET_REJECTED"
    status = 422

    def __init__(self, message: str, *, code: str | None = None, details: list[dict] | None = None) -> None:
        super().__init__(message, details=details)
        if code:
            self.code = code


class ImportError_(DomainError):
    """Base for import-time failures. Distinct name to avoid shadowing builtins.ImportError."""

    code = "IMPORT_ERROR"
    status = 422


class UnsupportedFileTypeError(ImportError_):
    code = "UNSUPPORTED_FILE_TYPE"
    status = 415


class FileTooLargeError(ImportError_):
    code = "FILE_TOO_LARGE"
    status = 413


class InvalidWorkbookError(ImportError_):
    code = "INVALID_WORKBOOK"
    status = 422


class ImportValidationError(ImportError_):
    """Row-level import validation failures, collected across the whole sheet."""

    code = "IMPORT_VALIDATION_FAILED"
    status = 422


class TooManyTasksError(ImportError_):
    code = "IMPORT_TOO_MANY_TASKS"
    status = 422


# --- AI agent / MCP --------------------------------------------------------


class AgentError(DomainError):
    """Base for the AI agent layer's own failures — distinct from a domain
    rejection the agent *reports* (e.g. a ChangeSet the scheduler rejected)."""

    code = "AGENT_ERROR"
    status = 502


class AiNotConfiguredError(AgentError):
    """No OPENROUTER_API_KEY/OPENROUTER_MODEL set. The rest of the app must
    keep working with this raised only from the chat endpoint."""

    code = "AI_NOT_CONFIGURED"
    status = 503


class AiProviderTimeoutError(AgentError):
    code = "AI_PROVIDER_TIMEOUT"
    status = 504


class AiProviderError(AgentError):
    """Malformed response, rate limit, non-2xx from OpenRouter, etc."""

    code = "AI_PROVIDER_ERROR"
    status = 502


class AgentStepLimitError(AgentError):
    """The loop hit AGENT_MAX_STEPS or AGENT_MAX_READ_TOOL_CALLS before
    resolving the request. No mutation happened."""

    code = "AGENT_STEP_LIMIT"
    status = 422


class AgentInvalidToolCallError(AgentError):
    """The model proposed a tool call this policy will not execute blindly —
    e.g. multiple apply_change_set calls in one turn, or malformed arguments
    that survive one correction attempt."""

    code = "AGENT_INVALID_TOOL_CALL"
    status = 422


class McpUnavailableError(AgentError):
    """The in-process MCP server/session could not be reached at all."""

    code = "MCP_UNAVAILABLE"
    status = 503


class McpToolError(AgentError):
    """The MCP transport itself reported an error for a tool call (as opposed
    to the tool returning a structured `ok: false` domain rejection)."""

    code = "MCP_TOOL_ERROR"
    status = 502
