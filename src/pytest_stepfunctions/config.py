"""Configuration registration and resolution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

DEFAULT_BACKEND = "auto"
DEFAULT_REGION = "us-east-1"
DEFAULT_LOCAL_ENDPOINT = "http://127.0.0.1:8083"


@dataclass(frozen=True, slots=True)
class ResolvedConfig:
    """Runtime configuration after CLI and ini resolution."""

    backend: str
    region: str
    local_endpoint: str
    role_arn: str | None
    definition_root: Path | None
    mock_config: Path | None
    validate: bool


def register_ini_options(parser: pytest.Parser) -> None:
    """Register `pyproject.toml` / ini backed plugin configuration."""

    parser.addini("sfn_backend", "Default Step Functions backend.", default=DEFAULT_BACKEND)
    parser.addini("sfn_region", "AWS region for Step Functions API calls.", default=DEFAULT_REGION)
    parser.addini(
        "sfn_local_endpoint",
        "Step Functions Local endpoint URL.",
        default=DEFAULT_LOCAL_ENDPOINT,
    )
    parser.addini("sfn_role_arn", "Role ARN for Step Functions calls.", default="")
    parser.addini(
        "sfn_definition_root",
        "Base directory for resolving ASL definition files.",
        default="",
    )
    parser.addini("sfn_mock_config", "Path to Step Functions Local mock config.", default="")
    parser.addini(
        "sfn_validate",
        "Validate definitions before execution when supported.",
        type="bool",
        default=False,
    )


def resolve_config(
    config: pytest.Config,
    *,
    marker_backend: str | None = None,
    override_backend: str | None = None,
    override_region: str | None = None,
    override_local_endpoint: str | None = None,
    override_role_arn: str | None = None,
    override_definition_root: str | Path | None = None,
    override_mock_config: str | Path | None = None,
    override_validate: bool | None = None,
) -> ResolvedConfig:
    """Resolve runtime config using fixture > marker > CLI > pyproject defaults."""

    cli_backend = _optional_str(config.getoption("sfn_backend"))
    cli_region = _optional_str(config.getoption("sfn_region"))
    cli_local_endpoint = _optional_str(config.getoption("sfn_local_endpoint"))
    cli_role_arn = _optional_str(config.getoption("sfn_role_arn"))
    cli_definition_root = _optional_str(config.getoption("sfn_definition_root"))
    cli_mock_config = _optional_str(config.getoption("sfn_mock_config"))
    cli_validate = bool(config.getoption("sfn_validate"))

    ini_backend = _optional_str(config.getini("sfn_backend")) or DEFAULT_BACKEND
    ini_region = _optional_str(config.getini("sfn_region")) or DEFAULT_REGION
    ini_local_endpoint = (
        _optional_str(config.getini("sfn_local_endpoint")) or DEFAULT_LOCAL_ENDPOINT
    )
    ini_role_arn = _optional_str(config.getini("sfn_role_arn"))
    ini_definition_root = _optional_str(config.getini("sfn_definition_root"))
    ini_mock_config = _optional_str(config.getini("sfn_mock_config"))
    ini_validate = bool(config.getini("sfn_validate"))

    backend = override_backend or marker_backend or cli_backend or ini_backend
    region = override_region or cli_region or ini_region
    local_endpoint = override_local_endpoint or cli_local_endpoint or ini_local_endpoint
    role_arn = override_role_arn or cli_role_arn or ini_role_arn
    definition_root = _path_from_value(
        override_definition_root or cli_definition_root or ini_definition_root
    )
    mock_config = _path_from_value(override_mock_config or cli_mock_config or ini_mock_config)
    validate = bool(
        override_validate if override_validate is not None else cli_validate or ini_validate
    )

    return ResolvedConfig(
        backend=backend,
        region=region,
        local_endpoint=local_endpoint,
        role_arn=role_arn,
        definition_root=definition_root,
        mock_config=mock_config,
        validate=validate,
    )


def _optional_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _path_from_value(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    return Path(value)
