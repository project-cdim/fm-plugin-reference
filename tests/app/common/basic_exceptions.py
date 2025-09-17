# Copyright 2025 NEC Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
#  under the License.

"""
Mock object of app.common.basic_exceptions
"""


class BaseHWControlError(Exception):
    """Mock class of BaseHWControlError."""

    def __init__(self, *args: object, additional_message: str = "") -> None:
        super().__init__(*args)
        self.additional_message = additional_message


class UnknownHWControlError(BaseHWControlError):
    """Mock class of UnknownHWControlError."""


class ControlObjectHWControlError(BaseHWControlError):
    """Mock class of ControlObjectHWControlError."""


class ConfigurationHWControlError(BaseHWControlError):
    """Mock class of ConfigurationHWControlError."""


class InternalHWControlError(BaseHWControlError):
    """Mock class of InternalHWControlError."""


class RequestConflictHWControlError(BaseHWControlError):
    """Mock class of RequestConflictHWControlError."""


class HostCPUNotFoundHWControlError(BaseHWControlError):
    """Mock class of HostCPUNotFoundHWControlError."""


class DeviceNotFoundHWControlError(BaseHWControlError):
    """Mock class of DeviceNotFoundHWControlError."""


class HostCPUAndDeviceNotFoundHWControlError(BaseHWControlError):
    """Mock class of HostCPUAndDeviceNotFoundHWControlError."""


class FMConnectFailureHWControlError(BaseHWControlError):
    """Mock class of FMConnectFailureHWControlError."""


class FMDisconnectFailureHWControlError(BaseHWControlError):
    """Mock class of FMDisconnectFailureHWControlError."""


class AuthenticationHWControlError(BaseHWControlError):
    """Mock class of AuthenticationHWControlError."""


class ResourceNotFoundHWControlError(BaseHWControlError):
    """Mock class of ResourceNotFoundHWControlError."""


class SwitchNotFoundHWControlError(BaseHWControlError):
    """Mock class of SwitchNotFoundHWControlError."""
