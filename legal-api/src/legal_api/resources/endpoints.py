# Copyright © 2021 Province of British Columbia
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
"""Mounting the end-points."""
from http import HTTPStatus
from typing import Optional

from flask import current_app, redirect, request, url_for, Flask  # noqa: I001
from registry_schemas import __version__ as registry_schemas_version  # noqa: I005

from legal_api import errorhandlers
from legal_api.utils.run_version import get_run_version

from .constants import EndpointEnum, EndpointVersionEnum
from .v2 import v2_endpoint


class Endpoints:
    """Manage the mounting, traversal and redirects for a set of versioned end-points."""

    app: Optional[Flask] = None

    def init_app(self, app: Flask):
        """Initialize the endpoints mapped for all services.

        Manages the versioned routes.
        Sets up redirects based on Accept headers or Versioned routes.
        """
        self.app = app
        self._handler_setup()
        self._mount_endpoints()

    def _handler_setup(self):

        @self.app.after_request
        def add_version(response):  # pylint: disable=unused-variable
            version = get_run_version()
            response.headers['API'] = f'legal_api/{version}'
            response.headers['SCHEMAS'] = f'registry_schemas/{registry_schemas_version}'
            return response

        errorhandlers.init_app(self.app)

    def _set_access_control_header(self, response):  # pylint: disable=unused-variable
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'

    def _mount_endpoints(self):
        """Mount the endpoints of the system."""
        v2_endpoint.init_app(self.app)

endpoints = Endpoints()
