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
"""Email processing rules and actions for Special Resolution notifications."""
from __future__ import annotations

import base64
import re
from http import HTTPStatus
from pathlib import Path

import requests
from entity_queue_common.service_utils import logger
from flask import current_app
from jinja2 import Template
from legal_api.models import Business, Filing, UserRoles

from entity_emailer.email_processors import get_filing_info, get_recipient_from_auth, substitute_template_parts


def _get_pdfs(
        status: str,
        token: str,
        business: dict,
        filing: Filing,
        filing_date_time: str,
        effective_date: str,
        name_changed: bool) -> list:
    # pylint: disable=too-many-locals, too-many-branches, too-many-statements, too-many-arguments
    """Get the pdfs for the incorporation output."""
    pdfs = []
    attach_order = 1
    headers = {
        'Accept': 'application/pdf',
        'Authorization': f'Bearer {token}'
    }

    if status == Filing.Status.PAID.value:
        # add filing pdf
        filing_pdf = requests.get(
            f'{current_app.config.get("LEGAL_API_URL")}'
            f'/businesses/{business["identifier"]}'
            f'/filings/{filing.id}/documents/specialResolutionApplication',
            headers=headers
        )
        if filing_pdf.status_code != HTTPStatus.OK:
            logger.error('Failed to get pdf for filing: %s', filing.id)
        else:
            filing_pdf_encoded = base64.b64encode(filing_pdf.content)
            pdfs.append(
                {
                    'fileName': 'Special Resolution Application.pdf',
                    'fileBytes': filing_pdf_encoded.decode('utf-8'),
                    'fileUrl': '',
                    'attachOrder': attach_order
                }
            )
            attach_order += 1
        corp_name = business.get('legalName')
        business_data = Business.find_by_internal_id(filing.business_id)
        receipt = requests.post(
            f'{current_app.config.get("PAY_API_URL")}/{filing.payment_token}/receipts',
            json={
                'corpName': corp_name,
                'filingDateTime': filing_date_time,
                'effectiveDateTime': effective_date if effective_date != filing_date_time else '',
                'filingIdentifier': str(filing.id),
                'businessNumber': business_data.tax_id if business_data and business_data.tax_id else ''
            },
            headers=headers
        )
        if receipt.status_code != HTTPStatus.CREATED:
            logger.error('Failed to get receipt pdf for filing: %s', filing.id)
        else:
            receipt_encoded = base64.b64encode(receipt.content)
            pdfs.append(
                {
                    'fileName': 'Receipt.pdf',
                    'fileBytes': receipt_encoded.decode('utf-8'),
                    'fileUrl': '',
                    'attachOrder': attach_order
                }
            )
            attach_order += 1
    if status == Filing.Status.COMPLETED.value:
        # specialResolution
        special_resolution = requests.get(
            f'{current_app.config.get("LEGAL_API_URL")}'
            f'/businesses/{business["identifier"]}'
            f'/filings/{filing.id}/documents/specialResolution',
            headers=headers
        )
        if special_resolution.status_code != HTTPStatus.OK:
            logger.error('Failed to get specialResolution pdf for filing: %s', filing.id)
        else:
            certificate_encoded = base64.b64encode(special_resolution.content)
            pdfs.append(
                {
                    'fileName': 'Special Resolution.pdf',
                    'fileBytes': certificate_encoded.decode('utf-8'),
                    'fileUrl': '',
                    'attachOrder': attach_order
                }
            )
            attach_order += 1
        # Change of Name
        if name_changed:
            name_change = requests.get(
                f'{current_app.config.get("LEGAL_API_URL")}/businesses/{business["identifier"]}/filings/{filing.id}'
                '?type=changeOfName',
                headers=headers
            )
            if name_change.status_code == HTTPStatus.OK:
                certified_name_change_encoded = base64.b64encode(name_change.content)
                pdfs.append(
                    {
                        'fileName': 'Change of Name Certified.pdf',
                        'fileBytes': certified_name_change_encoded.decode('utf-8'),
                        'fileUrl': '',
                        'attachOrder': attach_order
                    }
                )
                attach_order += 1
        # Certificate Rules
        rules = requests.get(
            f'{current_app.config.get("LEGAL_API_URL")}/businesses/{business["identifier"]}/filings/{filing.id}'
            '?type=certifiedRules',
            headers=headers
        )
        if rules.status_code == HTTPStatus.OK:
            certified_rules_encoded = base64.b64encode(rules.content)
            pdfs.append(
                {
                    'fileName': 'Certified Rules.pdf',
                    'fileBytes': certified_rules_encoded.decode('utf-8'),
                    'fileUrl': '',
                    'attachOrder': attach_order
                }
            )
            attach_order += 1

    return pdfs


def process(email_info: dict, token: str) -> dict:  # pylint: disable=too-many-locals, too-many-branches
    """Build the email for Special Resolution notification."""
    logger.debug('special_resolution_notification: %s', email_info)
    # get template and fill in parts
    filing_type, status = email_info['type'], email_info['option']
    # get template vars from filing
    filing, business, leg_tmz_filing_date, leg_tmz_effective_date = get_filing_info(email_info['filingId'])
    filing_name = filing.filing_type[0].upper() + ' '.join(re.findall('[a-zA-Z][^A-Z]*', filing.filing_type[1:]))

    template = Path(
        f'{current_app.config.get("TEMPLATE_PATH")}/SR-CP-{status}.html'
    ).read_text()
    filled_template = substitute_template_parts(template)
    # render template with vars
    jnja_template = Template(filled_template, autoescape=True)
    filing_data = (filing.json)['filing'][f'{filing_type}']
    name_changed = filing.filing_json['filing'].get('changeOfName')
    rules_changed = bool(filing.filing_json['filing'].get('restoration', {}).get('rulesFileKey'))
    html_out = jnja_template.render(
        business=business,
        filing=filing_data,
        header=(filing.json)['filing']['header'],
        filing_date_time=leg_tmz_filing_date,
        effective_date_time=leg_tmz_effective_date,
        entity_dashboard_url=current_app.config.get('DASHBOARD_URL') +
        (filing.json)['filing']['business'].get('identifier', ''),
        email_header=filing_name.upper(),
        filing_type=filing_type,
        name_changed=name_changed,
        rules_changed=rules_changed
    )

    # get attachments
    pdfs = _get_pdfs(status, token, business, filing, leg_tmz_filing_date, leg_tmz_effective_date, name_changed)

    # get recipients
    identifier = filing.filing_json['filing']['business']['identifier']
    recipients = []
    recipients.append(get_recipient_from_auth(identifier, token))

    if filing.submitter_roles and UserRoles.staff in filing.submitter_roles:
        # when staff file a sr due to client error, documentOptionalEmail may contain completing party email
        recipients.append(filing.filing_json['filing']['header'].get('documentOptionalEmail'))

    recipients = list(set(recipients))
    recipients = ', '.join(filter(None, recipients)).strip()

    # assign subject
    subject = ''
    if status == Filing.Status.PAID.value:
        subject = 'Confirmation of Special Resolution from the Business Registry'
    elif status == Filing.Status.COMPLETED.value:
        subject = 'Special Resolution Documents from the Business Registry'

    legal_name = business.get('legalName', None)
    subject = f'{legal_name} - {subject}' if legal_name else subject

    return {
        'recipients': recipients,
        'requestBy': 'BCRegistries@gov.bc.ca',
        'content': {
            'subject': subject,
            'body': f'{html_out}',
            'attachments': pdfs
        }
    }
