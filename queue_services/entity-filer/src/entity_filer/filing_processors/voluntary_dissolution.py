# Copyright © 2019 Province of British Columbia
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
"""File processing rules and actions for the Change of Name filing."""
from datetime import date
from typing import Dict

from entity_queue_common.service_utils import logger
from legal_api.models import Business


def process(business: Business, filing: Dict):
    """Render the annual_report onto the business model objects."""
    logger.debug('processing Voluntary Dissolution: %s', filing)
    dissolution_date = date.fromisoformat(filing['voluntaryDissolution'].get('dissolutionDate'))
    # Currently we don't use this for anything?
    # has_liabilities = filing['voluntaryDissolution'].get('hasLiabilities')
    business.dissolution_date = dissolution_date
