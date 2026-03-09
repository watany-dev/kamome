from __future__ import annotations

import importlib

import pytest_stepfunctions.backends as backends_module
import pytest_stepfunctions.backends.aws as aws_module
import pytest_stepfunctions.backends.base as base_module
import pytest_stepfunctions.backends.local as local_module
import pytest_stepfunctions.backends.teststate as teststate_module
import pytest_stepfunctions.config as config_module
import pytest_stepfunctions.definition as definition_module
import pytest_stepfunctions.exceptions as exceptions_module
import pytest_stepfunctions.markers as markers_module
import pytest_stepfunctions.validation as validation_module


def test_runtime_modules_can_be_reloaded() -> None:
    modules = [
        backends_module,
        aws_module,
        base_module,
        local_module,
        teststate_module,
        config_module,
        definition_module,
        exceptions_module,
        markers_module,
        validation_module,
    ]

    for module in modules:
        assert importlib.reload(module) is module
