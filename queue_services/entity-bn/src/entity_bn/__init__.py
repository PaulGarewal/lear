# Copyright © 2022 Province of British Columbia
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
"""The Entity Business Number service.

This module is the service worker for informing CRA about SP/GP registration and receive Business Number.
"""
from __future__ import annotations

import sentry_sdk
from flask import Flask
from legal_api.models import db
from legal_api.utils.run_version import get_run_version
from sentry_sdk.integrations.flask import FlaskIntegration

from .config import Config
from .config import Production
from .resources import register_endpoints
from .services import queue


def create_app(environment: Config = Production, **kwargs) -> Flask:
    """Return a configured Flask App using the Factory method."""
    app = Flask(__name__)
    app.config.from_object(environment)

    # Configure Sentry
    if dsn := app.config.get("SENTRY_DSN", None):
        sentry_sdk.init(
            dsn=dsn,
            integrations=[FlaskIntegration()],
            release=f"legal-api@{get_run_version()}",
            send_default_pii=False,
        )

    db.init_app(app)
    queue.init_app(app)
    register_endpoints(app)

    return app
