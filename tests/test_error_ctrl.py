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
Test program for _ErrorCtrl class
"""

from unittest import TestCase
import app.common.basic_exceptions as exc
from plugins.fm.reference.plugin import _ErrorCtrl, _ErrorType


class TestInit(TestCase):
    """Test class for constructor."""

    def test___init___error_list(self):
        """Test for error attribute initialization."""
        err = _ErrorCtrl()
        self.assertEqual([], err.error)


class TestPut(TestCase):
    """Test class for put method."""

    @classmethod
    def setUpClass(cls):
        cls.err = _ErrorCtrl()

    def tearDown(self):
        self.err.error = []

    def test_put_args_default(self):
        """Test when arguments are not specified."""
        self.err.put()
        self.assertEqual([_ErrorType.ERROR_CONTROL], self.err.error)

    def test_put_args_errno(self):
        """Test when arguments are specified."""
        self.err.put(_ErrorType.ERROR_INTERNAL)
        self.assertEqual([_ErrorType.ERROR_INTERNAL], self.err.error)

    def test_put_multi(self):
        """Test when executed multiple times."""
        self.err.put(_ErrorType.ERROR_INTERNAL)
        self.err.put(_ErrorType.ERROR_INCORRECT)
        expected = [_ErrorType.ERROR_INTERNAL, _ErrorType.ERROR_INCORRECT]
        self.assertEqual(expected, self.err.error)


class TestGet(TestCase):
    """Test class for raise_err method."""

    @classmethod
    def setUpClass(cls):
        cls.err = _ErrorCtrl()

    def tearDown(self):
        self.err.error = []

    def test_get_one_incorrect(self):
        """Test when only ERROR_INCORRECT is set."""
        self.err.put(_ErrorType.ERROR_INCORRECT)
        self.assertEqual(self.err.get(), exc.ConfigurationHwControlError)

    def test_get_one_control(self):
        """Test when only ERROR_CONTROL is set."""
        self.err.put(_ErrorType.ERROR_CONTROL)
        self.assertEqual(self.err.get(), exc.ControlObjectHwControlError)

    def test_get_one_internal(self):
        """Test when only ERROR_INTERNAL is set."""
        self.err.put(_ErrorType.ERROR_INTERNAL)
        self.assertEqual(self.err.get(), exc.InternalHwControlError)

    def test_get_error_not_set(self):
        """Test when no errors are set."""
        self.err.error = []
        self.assertEqual(self.err.get(), exc.InternalHwControlError)

    def test_get_all_factor_set(self):
        """Test when all errors are set."""
        for errno in _ErrorType:
            self.err.put(errno)
            self.err.put(errno)
        self.assertEqual(self.err.get(), exc.ConfigurationHwControlError)

    def test_get_multi_control(self):
        """Test for the priority of multiple errors (second one)."""
        self.err.put(_ErrorType.ERROR_CONTROL)
        self.err.put(_ErrorType.ERROR_INCORRECT)
        self.err.put(_ErrorType.ERROR_INTERNAL)
        self.assertEqual(self.err.get(), exc.ConfigurationHwControlError)

    def test_get_multi_internal(self):
        """Test for the priority of multiple errors (third one)."""
        self.err.put(_ErrorType.ERROR_INTERNAL)
        self.err.put(_ErrorType.ERROR_CONTROL)
        self.assertEqual(self.err.get(), exc.ControlObjectHwControlError)
