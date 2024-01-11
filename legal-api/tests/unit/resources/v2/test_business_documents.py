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

"""Tests to assure the business-summary end-point.

Test-Suite to ensure that the /businesses../summary endpoint works as expected.
"""
import copy
from http import HTTPStatus

from flask import current_app
from registry_schemas.example_data import (
    ALTERATION,
    FILING_HEADER,
    INCORPORATION_FILING_TEMPLATE,
)

from legal_api.models.document import Document, DocumentType
from legal_api.services.authz import STAFF_ROLE
from tests import integration_reports
from tests.unit import nested_session
from tests.unit.models import (
    factory_completed_filing,
    factory_incorporation_filing,
    factory_legal_entity,
)
from tests.unit.services.utils import create_header


@integration_reports
def test_get_document(requests_mock, session, client, jwt):
    """Assert that business summary is returned."""
    with nested_session(session):
        # setup
        identifier = "CP7654321"
        factory_legal_entity(identifier)
        requests_mock.post(current_app.config.get("REPORT_SVC_URL"), json={"foo": "bar"})
        headers = create_header(jwt, [STAFF_ROLE], identifier, **{"accept": "application/pdf"})
        # test
        rv = client.get(f"/api/v2/businesses/{identifier}/documents/summary", headers=headers)
        # check
        assert rv.status_code == HTTPStatus.OK
        assert requests_mock.called_once
        assert requests_mock.last_request._request.headers.get("Content-Type") == "application/json"


def test_get_document_invalid_business(session, client, jwt):
    """Assert that business summary is not returned."""
    with nested_session(session):
        # setup
        identifier = "CP7654321"
        factory_legal_entity(identifier)

        # test
        rv = client.get(
            "/api/v2/businesses/test/documents/summary", headers=create_header(jwt, [STAFF_ROLE], identifier)
        )
        # check
        assert rv.status_code == HTTPStatus.NOT_FOUND


def test_get_business_documents(session, client, jwt):
    """Assert that business summary is not returned."""
    with nested_session(session):
        # setup
        identifier = "CP7654321"
        factory_legal_entity(identifier)
        # test
        rv = client.get(
            f"/api/v2/businesses/{identifier}/documents", headers=create_header(jwt, [STAFF_ROLE], identifier)
        )
        # check
        assert rv.status_code == HTTPStatus.OK
        docs_json = rv.json
        assert docs_json["documents"]
        assert docs_json["documents"]["summary"]


def test_get_document_invalid_authorization(session, client, jwt):
    """Assert that business summary is not returned."""
    with nested_session(session):
        # setup
        identifier = "CP7654321"
        factory_legal_entity(identifier)
        # test
        rv = client.get(f"/api/v2/businesses/{identifier}/documents/summary")
        # check
        assert rv.status_code == HTTPStatus.UNAUTHORIZED


def test_get_coop_business_documents(session, client, jwt):
    """Assert that business documents have rules and memorandum."""
    with nested_session(session):
        identifier = "CP1234567"
        legal_entity = factory_legal_entity(identifier)

        INCORPORATION_APPLICATION = copy.deepcopy(INCORPORATION_FILING_TEMPLATE)
        INCORPORATION_APPLICATION["filing"]["incorporationApplication"]["nameRequest"]["nrNumber"] = "NR 1234567"
        INCORPORATION_APPLICATION["filing"]["incorporationApplication"]["nameRequest"][
            "legalName"
        ] = "legal_name-CP1234567"

        effective_date = INCORPORATION_APPLICATION["filing"]["header"]["effectiveDate"]
        filing = factory_incorporation_filing(legal_entity, INCORPORATION_APPLICATION, effective_date, effective_date)

        document_rules = Document()
        document_rules.type = DocumentType.COOP_RULES.value
        document_rules.file_key = "cooperative_rules.pdf"
        document_rules.file_name = "coops_rules.pdf"
        document_rules.content_type = "pdf"
        document_rules.legal_entity_id = legal_entity.id
        document_rules.filing_id = filing.id
        document_rules.save()
        assert document_rules.id

        document_memorandum = Document()
        document_memorandum.type = DocumentType.COOP_MEMORANDUM.value
        document_memorandum.file_key = "cooperative_memorandum.pdf"
        document_memorandum.file_name = "coops_memorandum.pdf"
        document_memorandum.content_type = "pdf"
        document_memorandum.legal_entity_id = legal_entity.id
        document_memorandum.filing_id = filing.id
        document_memorandum.save()
        assert document_memorandum.id

        rv = client.get(
            f"/api/v2/businesses/{identifier}/documents", headers=create_header(jwt, [STAFF_ROLE], identifier)
        )
        assert rv.status_code == HTTPStatus.OK
        docs_json = rv.json
        assert docs_json["documents"]
        assert docs_json["documents"]["certifiedRules"]
        assert docs_json["documents"]["certifiedMemorandum"]
        assert docs_json["documentsInfo"]["certifiedRules"]["uploaded"]
        assert docs_json["documentsInfo"]["certifiedRules"]["key"]
        assert docs_json["documentsInfo"]["certifiedRules"]["name"]
        assert docs_json["documentsInfo"]["certifiedMemorandum"]["uploaded"]
        assert docs_json["documentsInfo"]["certifiedMemorandum"]["key"]
        assert docs_json["documentsInfo"]["certifiedMemorandum"]["name"]

        # Testing scenario where we have a special resolution with the memorandum included in the resolution.
        filing = copy.deepcopy(FILING_HEADER)
        filing["filing"]["header"]["name"] = "specialResolution"
        filing["filing"]["alteration"] = copy.deepcopy(ALTERATION)
        filing["filing"]["alteration"]["memorandumInResolution"] = True
        filing["filing"]["alteration"]["rulesInResolution"] = True
        factory_completed_filing(legal_entity, filing)

        rv = client.get(
            f"/api/v2/businesses/{identifier}/documents", headers=create_header(jwt, [STAFF_ROLE], identifier)
        )
        assert rv.status_code == HTTPStatus.OK
        docs_json = rv.json
        assert docs_json["documents"]
        assert docs_json["documents"]["certifiedMemorandum"]
        assert docs_json["documents"]["certifiedRules"]
        assert docs_json["documentsInfo"]["certifiedRules"]["uploaded"]
        assert docs_json["documentsInfo"]["certifiedMemorandum"]["uploaded"]
        assert docs_json["documentsInfo"]["certifiedRules"]["includedInResolutionDate"]
        assert docs_json["documentsInfo"]["certifiedMemorandum"]["includedInResolutionDate"]
        assert docs_json["documentsInfo"]["certifiedRules"]["includedInResolution"]
        assert docs_json["documentsInfo"]["certifiedMemorandum"]["includedInResolution"]
        assert docs_json["documentsInfo"]["certifiedRules"]["key"]
        assert docs_json["documentsInfo"]["certifiedMemorandum"]["key"]
        assert docs_json["documentsInfo"]["certifiedRules"]["name"]
        assert docs_json["documentsInfo"]["certifiedMemorandum"]["name"]
