# Copyright © 2023 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""The Test Suites to ensure that the service is built and operating correctly."""
import datetime

EPOCH_DATETIME = datetime.datetime.utcfromtimestamp(0)
FROZEN_DATETIME = datetime.datetime(2001, 8, 5, 7, 7, 58, 272362)


class MockResponse:
    """Mock Response."""

    def __init__(self, status_code, text=None, json_data=None):
        """Mock Response __init__."""
        self.text = text
        self.content = text
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        """Mock Response json."""
        return self.json_data
