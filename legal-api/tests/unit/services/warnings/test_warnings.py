# Copyright © 2022 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in business with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Test suite to ensure Firms business checks work correctly."""
from unittest.mock import patch
from datetime import datetime

import pytest

from legal_api.services import check_warnings
from legal_api.services.warnings.business.business_checks import firms
from tests.unit.services.warnings import factory_party_role_person, factory_party_role_organization, factory_party_roles, \
    create_business, factory_address, create_filing

from legal_api.models import Address, LegalEntity, Office, PartyRole



@pytest.mark.parametrize(
    'test_name, entity_type, identifier, has_office, num_persons_roles, num_org_roles, filing_types, filing_has_completing_party, person_cessation_dates, org_cessation_dates, expected_code, expected_msg',
    [
        # SP tests
        ('SUCCESS', 'SP', 'FM0000001', True, 1, 0, ['registration'], [True], [None], [None], None, None),
        ('SUCCESS', 'SP', 'FM0000001', True, 0, 1, ['registration'], [True], [None], [None], None, None),
        ('SUCCESS', 'SP', 'FM0000001', True, 1, 0, ['registration', 'conversion'], [False, True], [None, None], [None, None], None, None),
        ('SUCCESS', 'SP', 'FM0000001', True, 0, 1, ['registration', 'conversion'], [False, True], [None, None], [None, None], None, None),
        ('FAIL_NO_PROPRIETOR', 'SP', 'FM0000001', True, 0, 0, ['registration'], [True], [None], [None], 'NO_PROPRIETOR', 'A proprietor is required.'),
        ('FAIL_NO_OFFICE', 'SP', 'FM0000001', False, 1, 0, ['registration'], [True], [None], [None], 'NO_BUSINESS_OFFICE', 'A business office is required.'),
        ('FAIL_NO_COMPLETING_PARTY', 'SP', 'FM0000001', True, 1, 0, ['registration'], [False], [None], [None], 'NO_COMPLETING_PARTY', 'A completing party is required.'),
        ('FAIL_CEASED_PROPRIETOR', 'SP', 'FM0000001', True, 1, 0, ['registration'], [True], [datetime.utcnow()], [None], 'NO_PROPRIETOR', 'A proprietor is required.'),
        ('FAIL_CEASED_PROPRIETOR', 'SP', 'FM0000001', True, 1, 0, ['registration', 'conversion'], [False, True], [datetime.utcnow(), datetime.utcnow()], [None, None], 'NO_PROPRIETOR', 'A proprietor is required.'),
        ('SUCCESS_CEASED_PROP', 'SP', 'FM0000001', True, 0, 1, ['registration'], [True], [datetime.utcnow()], [None], None, None),
        ('SUCCESS_CEASED_PROP', 'SP', 'FM0000001', True, 0, 1, ['registration', 'conversion'], [False, True], [datetime.utcnow(), datetime.utcnow()], [None, None], None, None),
        # GP tests
        ('SUCCESS', 'GP', 'FM0000001', True, 2, 0, ['registration'], [True], [None, None], [None, None], None, None),
        ('SUCCESS', 'GP', 'FM0000001', True, 0, 2, ['registration'], [True], [None, None], [None, None], None, None),
        ('SUCCESS', 'GP', 'FM0000001', True, 1, 1, ['registration'], [True], [None], [None], None, None),
        ('SUCCESS', 'GP', 'FM0000001', True, 2, 0, ['registration', 'conversion'], [False, True], [None, None], [None, None], None, None),
        ('SUCCESS', 'GP', 'FM0000001', True, 0, 2, ['registration', 'conversion'], [False, True], [None, None], [None, None], None, None),
        ('SUCCESS', 'GP', 'FM0000001', True, 1, 1, ['registration', 'conversion'], [False, True], [None], [None], None, None),
        ('FAIL_NO_PARTNER', 'GP', 'FM0000001', True, 0, 0, ['registration'], [True], [None, None], [None, None], 'NO_PARTNER', '2 partners are required.'),
        ('FAIL_NO_PARTNER', 'GP', 'FM0000001', True, 1, 0, ['registration'], [True], [None], [None], 'NO_PARTNER', '2 partners are required.'),
        ('FAIL_NO_PARTNER', 'GP', 'FM0000001', True, 0, 1, ['registration'], [True], [None], [None], 'NO_PARTNER', '2 partners are required.'),
        ('FAIL_NO_OFFICE', 'GP', 'FM0000001', False, 2, 0, ['registration'], [True], [None, None], [None, None], 'NO_BUSINESS_OFFICE', 'A business office is required.'),
        ('FAIL_NO_COMPLETING_PARTY', 'GP', 'FM0000001', True, 2, 0, ['registration'], [False], [None, None], [None, None], 'NO_COMPLETING_PARTY', 'A completing party is required.'),
        ('FAIL_CEASED_PARTNER', 'GP', 'FM0000001', True, 1, 1, ['registration'], [True], [datetime.utcnow()], [datetime.utcnow()], 'NO_PARTNER', '2 partners are required.'),
        ('FAIL_CEASED_PARTNER', 'GP', 'FM0000001', True, 1, 0, ['registration'], [True], [None], [datetime.utcnow()], 'NO_PARTNER', '2 partners are required.'),
        ('FAIL_CEASED_PARTNER', 'GP', 'FM0000001', True, 1, 0, ['registration', 'conversion'], [True, True], [None], [datetime.utcnow()], 'NO_PARTNER', '2 partners are required.'),
        ('FAIL_CEASED_PARTNER', 'GP', 'FM0000001', True, 0, 1, ['registration', 'conversion'], [False, True], [None], [datetime.utcnow()], 'NO_PARTNER', '2 partners are required.'),
        ('FAIL_CEASED_PARTNER', 'GP', 'FM0000001', True, 0, 2, ['registration', 'conversion'], [False, True], [None, None], [datetime.utcnow(), datetime.utcnow()], 'NO_PARTNER', '2 partners are required.'),
        ('SUCCESS_CEASED_PARTNER', 'GP', 'FM0000001', True, 2, 0, ['registration'], [True], [None, None], [datetime.utcnow(), datetime.utcnow()], None, None),
        ('SUCCESS_CEASED_PARTNER', 'GP', 'FM0000001', True, 2, 0, ['registration', 'conversion'], [True, True], [None, None], [datetime.utcnow(), datetime.utcnow()], None, None),
    ])
def test_check_warnings(session, test_name, entity_type, identifier, has_office, num_persons_roles:int,
                        num_org_roles:int, filing_types: list, filing_has_completing_party: list,
                        person_cessation_dates: list, org_cessation_dates:list, expected_code, expected_msg):
    """Assert that warnings check functions properly."""

    legal_entity =None

    create_business(entity_type=entity_type,
                    identifier=identifier,
                    create_office=has_office,
                    create_office_mailing_address=has_office,
                    create_office_delivery_address=has_office,
                    firm_num_persons_roles=num_persons_roles,
                    firm_num_org_roles=num_org_roles,
                    filing_types=filing_types,
                    filing_has_completing_party=filing_has_completing_party,
                    start_date=datetime.utcnow(),
                    person_cessation_dates=person_cessation_dates,
                    org_cessation_dates=org_cessation_dates)

    legal_entity =LegalEntity.find_by_identifier(identifier)
    assert legal_entity
    assert legal_entity.entity_type == entity_type
    assert legal_entity.identifier == identifier

    with patch.object(firms, 'check_address', return_value=[]):
        result = check_warnings(legal_entity)

    if expected_code:
        assert len(result) == 1
        warning = result[0]
        assert warning['code'] == expected_code
        assert warning['message'] == expected_msg
        assert warning['warningType'] == 'MISSING_REQUIRED_BUSINESS_INFO'
    else:
        assert len(result) == 0
