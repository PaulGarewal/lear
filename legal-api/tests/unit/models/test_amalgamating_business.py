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

"""
Tests to assure the AmalgamatingBusiness Model.
Test-Suite to ensure that the AmalgamatingBusiness Model is working as expected.

"""
from datetime import datetime

from registry_schemas.example_data import (
    ALTERATION_FILING_TEMPLATE,
    ANNUAL_REPORT,
    CHANGE_OF_DIRECTORS,
    CORRECTION_AR,
    COURT_ORDER,
    FILING_HEADER,
    SPECIAL_RESOLUTION,
)

from legal_api.models import AmalgamatingBusiness, Amalgamation, LegalEntity
from tests.unit.models import factory_filing, factory_legal_entity


def test_valid_amalgamating_business_save(session):
    """Assert that a valid amalgamating business can be saved."""
    b = factory_legal_entity("CP1234567")
    b.save()

    filing = factory_filing(b, ANNUAL_REPORT)
    filing.save()

    amalgamation = Amalgamation(
        amalgamation_type=Amalgamation.AmalgamationTypes.horizontal,
        legal_entity_id=b.id,
        filing_id=filing.id,
        amalgamation_date=datetime.utcnow(),
        court_approval=True,
    )

    amalgamation.save()

    amalgamating_business_1 = AmalgamatingBusiness(
        role=AmalgamatingBusiness.Role.amalgamating,
        foreign_jurisdiction="CA",
        foreign_jurisdiction_region="AB",
        foreign_name="Testing123",
        foreign_corp_num="123456789",
        legal_entity_id=b.id,
        amalgamation_id=amalgamation.id,
    )
    amalgamating_business_1.save()

    amalgamating_business_2 = AmalgamatingBusiness(
        role=AmalgamatingBusiness.Role.holding,
        foreign_jurisdiction="CA",
        foreign_jurisdiction_region="AB",
        foreign_name="Testing123",
        foreign_corp_num="123456789",
        legal_entity_id=b.id,
        amalgamation_id=amalgamation.id,
    )
    amalgamating_business_2.save()

    # verify
    assert amalgamating_business_1.id
    assert amalgamating_business_2.id
    for type in AmalgamatingBusiness.Role:
        assert type in [
            AmalgamatingBusiness.Role.holding,
            AmalgamatingBusiness.Role.amalgamating,
            AmalgamatingBusiness.Role.primary,
        ]
