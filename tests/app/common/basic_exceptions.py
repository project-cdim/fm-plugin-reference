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


class BaseHwControlError(Exception):
    """Mock class of BaseHwControlError."""
    def __init__(self, *args: object, additional_message: str = "") -> None:
        super().__init__(*args)
        self.additional_message = additional_message


class UnknownHwControlError(BaseHwControlError):
    """Mock class of UnknownHwControlError."""


class ControlObjectHwControlError(BaseHwControlError):
    """Mock class of ControlObjectHwControlError."""


class ConfigurationHwControlError(BaseHwControlError):
    """Mock class of ConfigurationHwControlError."""


class InternalHwControlError(BaseHwControlError):
    """Mock class of InternalConflictHwControlError."""


class RequestConflictHwControlError(BaseHwControlError):
    """Mock class of RequestConflictHwControlError."""


class HostCpuNotFoundHwControlError(BaseHwControlError):
    """Mock class of HostCpuNotFoundHwControlError."""


class DeviceNotFoundHwControlError(BaseHwControlError):
    """Mock class of DeviceNotFoundHwControlError."""


class HostCpuAndDeviceNotFoundHwControlError(BaseHwControlError):
    """Mock class of HostCpuAndDeviceNotFoundHwControlError."""


class FmConnectFailureHwControlError(BaseHwControlError):
    """Mock class of FmConnectFailureHwControlError."""


class FmDisconnectFailureHwControlError(BaseHwControlError):
    """Mock class of FmDisconnectFailureHwControlError."""


class AuthenticationHwControlError(BaseHwControlError):
    """Mock class of AuthenticationHwControlError."""


class ResourceNotFoundHwControlError(BaseHwControlError):
    """Mock class of ResourceNotFoundHwControlError."""


class SwitchNotFoundHwControlError(BaseHwControlError):
    """Mock class of SwitchNotFoundHwControlError."""
