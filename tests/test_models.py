from __future__ import annotations

from toolchain.models import APIError, NetworkError, ToolchainError, UserInputError


def test_user_input_error_exit_code_1():
    assert UserInputError("bad flag").exit_code == 1


def test_api_error_exit_code_2():
    assert APIError("500").exit_code == 2


def test_network_error_exit_code_3():
    assert NetworkError("timeout").exit_code == 3


def test_all_are_toolchain_errors():
    assert issubclass(UserInputError, ToolchainError)
    assert issubclass(APIError, ToolchainError)
    assert issubclass(NetworkError, ToolchainError)
