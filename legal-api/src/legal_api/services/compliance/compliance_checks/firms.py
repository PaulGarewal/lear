# Copyright © 2022 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Compliance checks for firms."""


from legal_api.models import Address, Business, Filing, Office, Party, PartyRole

from . import (ComplianceWarnings,   # noqa: I001
               ComplianceWarningCodes,   # noqa: I001
               ComplianceWarningReferers,   # noqa: I001
               get_address_compliance_warning)   # noqa: I001


def check_compliance(business: Business) -> list:
    """Check for non-compliant business data."""
    result = []

    legal_type = business.legal_type

    result.extend(check_office(business))
    result.extend(check_parties(legal_type, business))

    return result


def check_office(business: Business) -> list:
    """Check for non-compliant office data."""
    result = []

    business_office = business.offices \
        .filter(Office.office_type == 'businessOffice') \
        .one_or_none()

    if not business_office:
        result.append({
            'code': ComplianceWarningCodes.NO_BUSINESS_OFFICE,
            'message': 'A business office is required.',
        })
        return result

    mailing_address = business_office.addresses \
        .filter(Address.address_type == 'mailing') \
        .one_or_none()
    result.extend(check_address(mailing_address, Address.MAILING, ComplianceWarningReferers.BUSINESS_OFFICE))

    delivery_address = business_office.addresses \
        .filter(Address.address_type == 'delivery') \
        .one_or_none()
    result.extend(check_address(delivery_address, Address.DELIVERY, ComplianceWarningReferers.BUSINESS_OFFICE))

    return result


def check_parties(legal_type: str, business: Business) -> list:
    """Check for non-compliant parties data."""
    result = []

    firm_party_roles = business.party_roles.all()
    result.extend(check_firm_parties(legal_type, firm_party_roles))

    completing_party_filing = Filing \
        .get_most_recent_legal_filing(business.id, 'conversion')

    if not completing_party_filing:
        completing_party_filing = Filing \
            .get_most_recent_legal_filing(business.id, 'registration')

    result.extend(check_completing_party_for_filing(completing_party_filing))
    return result


def check_firm_parties(legal_type: str, party_roles: list) -> list:
    """Check for non-compliant firm parties data."""
    result = []

    proprietor_parties = []
    partner_parties = []

    for party_role in party_roles:
        if party_role.role == PartyRole.RoleTypes.PROPRIETOR.value:
            proprietor_parties.append(party_role.party)
            result.extend(check_firm_party(legal_type, party_role))
        if party_role.role == PartyRole.RoleTypes.PARTNER.value:
            partner_parties.append(party_role.party)
            result.extend(check_firm_party(legal_type, party_role))

    if legal_type == Business.LegalTypes.SOLE_PROP.value and not proprietor_parties:
        result.append({
            'code': ComplianceWarningCodes.NO_PROPRIETOR,
            'message': 'A proprietor is required.',
        })
    elif legal_type == Business.LegalTypes.PARTNERSHIP.value and len(partner_parties) < 2:
        result.append({
            'code': ComplianceWarningCodes.NO_PARTNER,
            'message': '2 partners are required.',
        })

    return result


def check_completing_party_for_filing(filing: Filing) -> list:
    """Check for non-compliant completing party data for conversion or registration filing."""
    result = []

    if not filing:
        result.append({
            'code': ComplianceWarningCodes.NO_COMPLETING_PARTY,
            'message': 'A completing party is required.',
        })
        return result

    completing_party_role = filing.filing_party_roles \
        .filter(PartyRole.role == PartyRole.RoleTypes.COMPLETING_PARTY.value) \
        .one_or_none()

    if not completing_party_role:
        result.append({
            'code': ComplianceWarningCodes.NO_COMPLETING_PARTY,
            'message': 'A completing party is required.',
        })
        return result

    result.extend(check_completing_party(completing_party_role))
    return result


# pylint: disable=too-many-branches;
def check_firm_party(legal_type: str, party_role: PartyRole):
    """Check for non-compliant firm party data."""
    result = []

    party = party_role.party
    role = party_role.role.replace('_', ' ').title()
    no_person_name_check_warning = False
    no_org_name_warning = False
    no_org_identifier_warning = False

    if party.party_type == Party.PartyTypes.PERSON.value:
        if not party.first_name and not party.last_name:
            no_person_name_check_warning = True
        result.extend(check_address(party.mailing_address, Address.MAILING, ComplianceWarningReferers.BUSINESS_PARTY))
    elif party.party_type == Party.PartyTypes.ORGANIZATION.value:
        if not party.organization_name:
            no_org_name_warning = True
        if legal_type == Business.LegalTypes.SOLE_PROP.value and not party.identifier:
            no_org_identifier_warning = True
        result.extend(check_address(party.mailing_address, Address.MAILING, ComplianceWarningReferers.BUSINESS_PARTY))

    if legal_type == Business.LegalTypes.SOLE_PROP.value:
        if no_person_name_check_warning:
            result.append({
                'code': ComplianceWarningCodes.NO_PROPRIETOR_PERSON_NAME,
                'message': f'{role} name is required.',
            })
        if no_org_name_warning:
            result.append({
                'code': ComplianceWarningCodes.NO_PROPRIETOR_ORG_NAME,
                'message': f'{role} organization name is required.',
            })
        if no_org_identifier_warning:
            result.append({
                'code': ComplianceWarningCodes.NO_PROPRIETOR_ORG_IDENTIFIER,
                'message': f'{role} organization identifier is required.',
            })
    elif legal_type == Business.LegalTypes.PARTNERSHIP.value:
        if no_person_name_check_warning:
            result.append({
                'code': ComplianceWarningCodes.NO_PARTNER_PERSON_NAME,
                'message': f'{role} name is required.',
            })
        if no_org_name_warning:
            result.append({
                'code': ComplianceWarningCodes.NO_PARTNER_ORG_NAME,
                'message': f'{role} organization name is required.',
            })

    return result


def check_completing_party(party_role: PartyRole):
    """Check for non-compliant completing party data."""
    result = []

    party = party_role.party
    role = party_role.role.replace('_', ' ').title()

    if party.party_type == Party.PartyTypes.PERSON.value:
        if not party.first_name and not party.last_name:
            result.append({
                'code': ComplianceWarningCodes.NO_COMPLETING_PARTY_PERSON_NAME,
                'message': f'{role} name is required.',
            })
        result.extend(check_address(party.mailing_address, Address.MAILING, ComplianceWarningReferers.COMPLETING_PARTY))
    elif party.party_type == Party.PartyTypes.ORGANIZATION.value:
        if not party.organization_name:
            result.append({
                'code': ComplianceWarningCodes.NO_COMPLETING_PARTY_ORG_NAME,
                'message': f'{role} organization name is required.',
            })
        if not party.identifier:
            result.append({
                'code': ComplianceWarningCodes.NO_COMPLETING_PARTY_ORG_IDENTIFIER,
                'message': f'{role} organization identifier is required.',
            })

        result.extend(check_address(party.mailing_address, Address.MAILING, ComplianceWarningReferers.COMPLETING_PARTY))

    return result


def check_address(address: Address,
                  address_type: str,
                  referer: ComplianceWarningReferers) -> list:
    """Check for non-compliant address data."""
    result = []

    if not address:
        result.append(get_address_compliance_warning(referer,
                                                     address_type,
                                                     ComplianceWarnings.NO_ADDRESS))
        return result

    if not address.street:
        result.append(get_address_compliance_warning(referer,
                                                     address_type,
                                                     ComplianceWarnings.NO_ADDRESS_STREET))
    if not address.city:
        result.append(get_address_compliance_warning(referer,
                                                     address_type,
                                                     ComplianceWarnings.NO_ADDRESS_CITY))
    if not address.country:
        result.append(get_address_compliance_warning(referer,
                                                     address_type,
                                                     ComplianceWarnings.NO_ADDRESS_COUNTRY))
    if not address.postal_code:
        result.append(get_address_compliance_warning(referer,
                                                     address_type,
                                                     ComplianceWarnings.NO_ADDRESS_POSTAL_CODE))
    if not address.region:
        result.append(get_address_compliance_warning(referer,
                                                     address_type,
                                                     ComplianceWarnings.NO_ADDRESS_REGION))

    return result
