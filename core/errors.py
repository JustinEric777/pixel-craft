"""Errors shared by core rules and feature use cases."""

from __future__ import annotations


class CoreError(Exception):
    """Base error with an HTTP mapping understood by the interface layer."""

    status_code = 400


class ProjectNotFoundError(CoreError):
    status_code = 404


class EditNotFoundError(CoreError):
    status_code = 404


class UnknownCapabilityError(CoreError):
    status_code = 404


class CapabilityConflictError(CoreError):
    status_code = 409


class UnsupportedMediaTypeError(CoreError):
    status_code = 415


class AssetRequiredError(CoreError):
    status_code = 400


class UnknownAssetError(CoreError):
    status_code = 404


class ParameterValidationError(CoreError):
    status_code = 422


class ModelExecutionError(CoreError):
    status_code = 503


class JobNotFoundError(CoreError):
    status_code = 404


class WorkflowNotFoundError(CoreError):
    status_code = 404


class WorkflowInputError(CoreError):
    status_code = 400


class WorkflowStateError(CoreError):
    status_code = 409
