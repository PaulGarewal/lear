# Copyright © 2020 Province of British Columbia
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

"""This provides the service for getting business details as of a filing."""
# pylint: disable=singleton-comparison ; pylint does not recognize sqlalchemy ==
from datetime import datetime

import pycountry
from sql_versioning import history_cls
from sqlalchemy import or_
from sqlalchemy.sql.expression import null
from sqlalchemy_continuum import version_class

from legal_api.models import (
    Address,
    Alias,
    ColinEntity,
    EntityRole,
    Filing,
    LegalEntity,
    Office,
    Resolution,
    ShareClass,
    ShareSeries,
    db,
)
from legal_api.utils.legislation_datetime import LegislationDatetime


class VersionedBusinessDetailsService:  # pylint: disable=too-many-public-methods
    """Provides service for getting business details as of a filing."""

    @staticmethod
    def get_revision(filing_id, legal_entity_id):
        """Consolidates based on filing type upto the given transaction id of a filing."""
        legal_entity = LegalEntity.find_by_internal_id(legal_entity_id)
        filing = Filing.find_by_id(filing_id)

        revision_json = {}
        revision_json['filing'] = {}
        if filing.filing_type == 'incorporationApplication':
            revision_json['filing'] = \
                VersionedBusinessDetailsService.get_ia_revision(filing, legal_entity)
        elif filing.filing_type == 'changeOfDirectors':
            revision_json['filing'] = \
                VersionedBusinessDetailsService.get_cod_revision(filing, legal_entity)
        elif filing.filing_type == 'changeOfAddress':
            revision_json['filing'] = \
                VersionedBusinessDetailsService.get_coa_revision(filing, legal_entity)
        elif filing.filing_type == 'annualReport':
            revision_json['filing'] = \
                VersionedBusinessDetailsService.get_ar_revision(filing, legal_entity)
        elif filing.filing_type == 'correction':
            revision_json = filing.json

            # This is required to find diff
            for party in revision_json.get('filing', {}).get('incorporationApplication', {}).get('parties', []):
                party['id'] = party.get('officer', {}).get('id', None)
                for party_role in party['roles']:
                    party_role['id'] = party_role['roleType']

        # filing_type's yet to be handled alteration, changeOfName, specialResolution, voluntaryDissolution
        if not revision_json['filing']:
            revision_json = filing.json
            revision_json['filing']['business'] = \
                VersionedBusinessDetailsService.get_business_revision(filing.transaction_id, legal_entity)

        revision_json['filing']['header'] = VersionedBusinessDetailsService.get_header_revision(filing)

        return revision_json

    @staticmethod
    def get_ia_revision(filing, legal_entity) -> dict:
        """Consolidates incorporation application upto the given transaction id of a filing."""
        ia_json = {}

        ia_json['business'] = \
            VersionedBusinessDetailsService.get_business_revision(filing.transaction_id, legal_entity)
        ia_json['incorporationApplication'] = {}
        ia_json['incorporationApplication']['offices'] = \
            VersionedBusinessDetailsService.get_office_revision(filing.transaction_id, legal_entity.id)
        ia_json['incorporationApplication']['parties'] = \
            VersionedBusinessDetailsService.get_party_role_revision(filing.transaction_id,
                                                                    legal_entity.id, is_ia_or_after=True)
        ia_json['incorporationApplication']['nameRequest'] = \
            VersionedBusinessDetailsService.get_name_request_revision(filing)
        ia_json['incorporationApplication']['contactPoint'] = \
            VersionedBusinessDetailsService.get_contact_point_revision(filing)
        ia_json['incorporationApplication']['shareStructure'] = {}
        ia_json['incorporationApplication']['shareStructure']['shareClasses'] = \
            VersionedBusinessDetailsService.get_share_class_revision(filing.transaction_id, legal_entity.id)
        ia_json['incorporationApplication']['nameTranslations'] = \
            VersionedBusinessDetailsService.get_name_translations_revision(filing.transaction_id, legal_entity.id)
        ia_json['incorporationApplication']['incorporationAgreement'] = \
            VersionedBusinessDetailsService.get_incorporation_agreement_json(filing)

        # setting completing party email from filing json
        party_email = ''
        for party in filing.json['filing']['incorporationApplication']['parties']:
            if next((x for x in party['roles'] if x['roleType'] == 'Completing Party'), None):
                party_email = party.get('officer', {}).get('email', None)
                break

        for party in ia_json['incorporationApplication']['parties']:
            if next((x for x in party['roles'] if x['roleType'] == 'Completing Party'), None):
                party['officer']['email'] = party_email
                break

        return ia_json

    @staticmethod
    def get_cod_revision(filing, legal_entity) -> dict:
        """Consolidates change of directors upto the given transaction id of a filing."""
        cod_json = {}

        cod_json['business'] = \
            VersionedBusinessDetailsService.get_business_revision(filing.transaction_id, legal_entity)
        cod_json['changeOfDirectors'] = {}
        cod_json['changeOfDirectors']['directors'] = \
            VersionedBusinessDetailsService.get_party_role_revision(filing.transaction_id,
                                                                    legal_entity.id, role='director')
        return cod_json

    @staticmethod
    def get_coa_revision(filing, legal_entity) -> dict:
        """Consolidates change of address upto the given transaction id of a filing."""
        coa_json = {}

        coa_json['business'] = \
            VersionedBusinessDetailsService.get_business_revision(filing.transaction_id, legal_entity)
        coa_json['changeOfAddress'] = {}
        coa_json['changeOfAddress']['offices'] = \
            VersionedBusinessDetailsService.get_office_revision(filing.transaction_id, legal_entity.id)
        coa_json['changeOfAddress']['legalType'] = coa_json['business']['legalType']
        return coa_json

    @staticmethod
    def get_ar_revision(filing, legal_entity) -> dict:
        """Consolidates annual report upto the given transaction id of a filing."""
        ar_json = {}

        ar_json['business'] = \
            VersionedBusinessDetailsService.get_business_revision(filing, legal_entity)

        ar_json['annualReport'] = {}
        if legal_entity.last_ar_date:
            ar_json['annualReport']['annualReportDate'] = legal_entity.last_ar_date.date().isoformat()
        if legal_entity.last_agm_date:
            ar_json['annualReport']['annualGeneralMeetingDate'] = legal_entity.last_agm_date.date().isoformat()

        if 'didNotHoldAgm' in filing.json['filing']['annualReport']:
            ar_json['annualReport']['didNotHoldAgm'] = filing.json['filing']['annualReport']['didNotHoldAgm']

        if 'nextARDate' in filing.json['filing']['annualReport']:
            ar_json['annualReport']['nextARDate'] = filing.json['filing']['annualReport']['nextARDate']

        ar_json['annualReport']['directors'] = \
            VersionedBusinessDetailsService.get_party_role_revision(filing,
                                                                    legal_entity.id, role='director')
        ar_json['annualReport']['offices'] = \
            VersionedBusinessDetailsService.get_office_revision(filing, legal_entity.id)

        # legal_type CP may need changeOfDirectors/changeOfAddress
        if 'changeOfDirectors' in filing.json['filing']:
            ar_json['changeOfDirectors'] = {}
            ar_json['changeOfDirectors']['directors'] = ar_json['annualReport']['directors']

        if 'changeOfAddress' in filing.json['filing']:
            ar_json['changeOfAddress'] = {}
            ar_json['changeOfAddress']['offices'] = ar_json['annualReport']['offices']
            ar_json['changeOfAddress']['legalType'] = ar_json['business']['legalType']

        return ar_json

    @staticmethod
    def get_header_revision(filing) -> dict:
        """Retrieve header from filing."""
        _header = filing.json['filing']['header']
        return _header

    @staticmethod
    def get_company_details_revision(filing_id, legal_entity_id) -> dict:
        """Consolidates company details upto the given transaction id of a filing."""
        company_profile_json = {}
        legal_entity = LegalEntity.find_by_internal_id(legal_entity_id)
        filing = Filing.find_by_id(filing_id)
        company_profile_json['business'] = \
            VersionedBusinessDetailsService.get_business_revision(filing.transaction_id, legal_entity)
        company_profile_json['parties'] = \
            VersionedBusinessDetailsService.get_party_role_revision(filing.transaction_id, legal_entity_id)
        company_profile_json['offices'] = \
            VersionedBusinessDetailsService.get_office_revision(filing.transaction_id, legal_entity_id)
        company_profile_json['shareClasses'] = \
            VersionedBusinessDetailsService.get_share_class_revision(filing.transaction_id, legal_entity_id)
        company_profile_json['nameTranslations'] = \
            VersionedBusinessDetailsService.get_name_translations_revision(filing.transaction_id, legal_entity_id)
        company_profile_json['resolutions'] = \
            VersionedBusinessDetailsService.get_resolution_dates_revision(filing.transaction_id, legal_entity_id)
        return company_profile_json

    @staticmethod
    def get_business_revision(filing, legal_entity) -> dict:
        """Consolidates the business info as of a particular transaction."""
        filing_id = filing.id

        # The history table has the old revisions, not the current one.
        if not(le_revision := db.session.query(LegalEntity) \
                .filter(or_(LegalEntity.change_filing_id <= filing_id,
                            LegalEntity.change_filing_id == None)) \
                .filter(LegalEntity.id == legal_entity.id).one_or_none()
        ):
            legal_entity_version = history_cls(legal_entity)
            le_revision = db.session.query(legal_entity_version) \
            .filter(legal_entity_version.change_filing_id <= filing_id) \
            .filter(legal_entity_version.id == legal_entity.id) \
            .order_by(legal_entity_version.change_filing_id).first()

        return VersionedBusinessDetailsService.business_revision_json(le_revision, legal_entity.json())


    @staticmethod
    def get_business_revision_obj(transaction_id, legal_entity):
        """Return business version object associated with a given transaction id for a LegalEntity."""
        business_version = version_class(LegalEntity)
        business_revision = db.session.query(business_version) \
            .filter(business_version.transaction_id <= transaction_id) \
            .filter(business_version.operation_type != 2) \
            .filter(business_version.id == legal_entity.id) \
            .filter(or_(business_version.end_transaction_id == None,  # pylint: disable=singleton-comparison # noqa: E711,E501;
                        business_version.end_transaction_id > transaction_id)) \
            .order_by(business_version.transaction_id).one_or_none()
        return business_revision

    @staticmethod
    def find_last_value_from_business_revision(transaction_id, legal_entity_id,
                                               is_dissolution_date=False,
                                               is_restoration_expiry_date=False) -> dict:
        """Get business info with last value of dissolution_date or restoration_expiry_date."""
        business_version = version_class(LegalEntity)
        query = db.session.query(business_version) \
            .filter(business_version.transaction_id < transaction_id) \
            .filter(business_version.operation_type != 2) \
            .filter(business_version.id == legal_entity_id)
        if is_dissolution_date:
            query = query.filter(business_version.dissolution_date != None)  # pylint: disable=singleton-comparison # noqa: E711,E501;
        if is_restoration_expiry_date:
            query = query.filter(business_version.restoration_expiry_date != None)  # pylint: disable=singleton-comparison # noqa: E711,E501;
        business_revision = query.order_by(business_version.transaction_id.desc()).first()
        return business_revision

    @staticmethod
    def get_business_revision_after_filing(filing_id, legal_entity_id) -> dict:
        """Consolidates the business info as of a particular transaction."""
        legal_entity = LegalEntity.find_by_internal_id(legal_entity_id)
        # set the revision to the current state, makes the IF easier
        business_revision = legal_entity
        if legal_entity.change_filing_id != filing_id:
            # it's not current for the filing, so get the most recent
            # revision for the filing
            business_history = history_cls(LegalEntity)
            business_revision = db.session.query(business_history) \
                .filter(business_history.change_filing_id <= filing_id) \
                .filter(business_history.id == legal_entity_id) \
                .order_by(business_history.change_filing_id).first()

        return VersionedBusinessDetailsService.business_revision_json(business_revision, legal_entity.json())


    @staticmethod
    def get_office_revision(filing, legal_entity_id) -> dict:
        """Consolidates all office changes upto the given transaction id."""
        filing_id = filing.id
        offices_json = {}
        # address_version = version_class(Address)
        # offices_version = version_class(Office)

        # offices = db.session.query(offices_version) \
        #     .filter(offices_version.transaction_id <= transaction_id) \
        #     .filter(offices_version.operation_type != 2) \
        #     .filter(offices_version.legal_entity_id == legal_entity_id) \
        #     .filter(or_(offices_version.end_transaction_id == None,  # pylint: disable=singleton-comparison # noqa: E711,E501;
        #                 offices_version.end_transaction_id > transaction_id)) \
        #     .order_by(offices_version.transaction_id).all()

        # for office in offices:
        #     offices_json[office.office_type] = {}
        #     addresses_list = db.session.query(address_version) \
        #         .filter(address_version.transaction_id <= transaction_id) \
        #         .filter(address_version.operation_type != 2) \
        #         .filter(address_version.office_id == office.id) \
        #         .filter(or_(address_version.end_transaction_id == None,  # pylint: disable=singleton-comparison # noqa: E711,E501;
        #                     address_version.end_transaction_id > transaction_id)) \
        #         .order_by(address_version.transaction_id).all()
        #     for address in addresses_list:
        #         offices_json[office.office_type][f'{address.address_type}Address'] = \
        #             VersionedBusinessDetailsService.address_revision_json(address)

        # HERE
        filing_id = filing.id
        address_history = history_cls(Address)
        office_history = history_cls(Office)

        offices_current = db.session.query(Office, null().label("changed")) \
            .filter(Office.change_filing_id <= filing_id) \
            .filter(Office.legal_entity_id == legal_entity_id) \
            .filter(Office.deactivated_date is null())

        offices_historical = db.session.query(office_history) \
            .filter(office_history.change_filing_id <= filing_id) \
            .filter(office_history.legal_entity_id == legal_entity_id)  \
            .filter(Office.deactivated_date > filing.effective_date)

        # Get all of the valid types in effect for this LegalEntity and Filing
        current_types = db.session.query(Office.office_type) \
            .filter(Office.change_filing_id <= filing_id) \
            .filter(Office.legal_entity_id == legal_entity_id) \
            .filter(Office.deactivated_date is null())
        historical_types = db.session.query(office_history.office_type) \
            .filter(office_history.change_filing_id <= filing_id) \
            .filter(office_history.legal_entity_id == legal_entity_id) \
            .filter(Office.deactivated_date > filing.effective_date)

        valid_office_types = current_types.union(historical_types).distinct().all()

        for valid_office_type in valid_office_types:

            office = offices_current.filter(Office.office_type == valid_office_type) \
                    .union(offices_historical.filter(office_history.office_type == valid_office_type)) \
                    .first()

            offices_json[office.office_type] = {}

            # addresses_list = db.session.query(Address) \

            # addresses_list = db.session.query(address_history) \
            #     .filter(address_history.transaction_id <= filing_id) \
            #     .filter(address_history.office_id == office.id) \
            #     .order_by(address_history.change_filing_id).first()
            # for address in addresses_list:
            #     offices_json[office.office_type][f'{address.address_type}Address'] = \
            #         VersionedBusinessDetailsService.address_revision_json(address)

        return offices_json

    @staticmethod
    def get_party_role_revision(filing, legal_entity_id, is_ia_or_after=False, role=None) -> dict:
        """Consolidates all party changes upto the given transaction id."""
        # party_role_version = version_class(EntityRole)
        # party_roles = db.session.query(party_role_version)\
        #     .filter(party_role_version.transaction_id <= transaction_id) \
        #     .filter(party_role_version.operation_type != 2) \
        #     .filter(party_role_version.legal_entity_id == legal_entity_id) \
        #     .filter(or_(role == None,  # pylint: disable=singleton-comparison # noqa: E711,E501;
        #                 party_role_version.role_type == role)) \
        #     .filter(or_(party_role_version.end_transaction_id == None,   # pylint: disable=singleton-comparison # noqa: E711,E501;
        #                 party_role_version.end_transaction_id > transaction_id)) \
        #     .order_by(party_role_version.transaction_id).all()
        # parties = []
        # for party_role in party_roles:
        #     if party_role.cessation_date is None:
        #         party_role_json = VersionedBusinessDetailsService.party_role_revision_json(transaction_id,
        #                                                                                    party_role, is_ia_or_after)
        #         if 'roles' in party_role_json and (party := next((x for x in parties if x['officer']['id']
        #                                                           == party_role_json['officer']['id']), None)):
        #             party['roles'].extend(party_role_json['roles'])
        #         else:
        #             parties.append(party_role_json)

        # return parties
        # HERE
        filing_id = filing.id
        filing_date = filing.effective_date
        entity_role_version = history_cls(EntityRole)

        entity_roles_current = db.session.query(EntityRole, null().label("changed"))\
            .filter(EntityRole.change_filing_id <= filing_id) \
            .filter(EntityRole.legal_entity_id == legal_entity_id) \
            .filter(EntityRole.cessation_date is null()) \
            .filter(or_(role == None,  # pylint: disable=singleton-comparison # noqa: E711,E501;
                        EntityRole.role_type == role))

        entity_roles_historical = db.session.query(entity_role_version)\
            .filter(entity_role_version.change_filing_id <= filing_id) \
            .filter(entity_role_version.legal_entity_id == legal_entity_id) \
            .filter(or_(entity_role_version.cessation_date is null(),
                        entity_role_version.change_filing_id <= filing_id)) \
            .filter(or_(role is null(),
                        entity_role_version.role_type == role))

        entity_roles = entity_roles_current.union(entity_roles_historical) \
            .order_by(entity_role_version.filing_id).all()

        parties = []
        for party_role in entity_roles:
            if party_role.cessation_date is None:
                party_role_json = VersionedBusinessDetailsService.party_role_revision_json(transaction_id,
                                                                                           party_role, is_ia_or_after)
                if 'roles' in party_role_json and (party := next((x for x in parties if x['officer']['id']
                                                                  == party_role_json['officer']['id']), None)):
                    party['roles'].extend(party_role_json['roles'])
                else:
                    parties.append(party_role_json)

        return parties

    @staticmethod
    def get_share_class_revision(transaction_id, legal_entity_id) -> dict:
        """Consolidates all share classes upto the given transaction id."""
        share_class_version = version_class(ShareClass)
        share_classes_list = db.session.query(share_class_version) \
            .filter(share_class_version.transaction_id <= transaction_id) \
            .filter(share_class_version.operation_type != 2) \
            .filter(share_class_version.legal_entity_id == legal_entity_id) \
            .filter(or_(share_class_version.end_transaction_id == None,  # pylint: disable=singleton-comparison # noqa: E711,E501;
                        share_class_version.end_transaction_id > transaction_id)) \
            .order_by(share_class_version.transaction_id).all()
        share_classes = []
        for share_class in share_classes_list:
            share_class_json = VersionedBusinessDetailsService.share_class_revision_json(share_class)
            share_class_json['series'] = VersionedBusinessDetailsService.get_share_series_revision(transaction_id,
                                                                                                   share_class.id)
            share_class_json['type'] = 'Class'
            share_class_json['id'] = str(share_class_json['id'])
            share_classes.append(share_class_json)
        return share_classes

    @staticmethod
    def get_share_series_revision(transaction_id, share_class_id) -> dict:
        """Consolidates all share series under the share class upto the given transaction id."""
        share_series_version = version_class(ShareSeries)
        share_series_list = db.session.query(share_series_version) \
            .filter(share_series_version.transaction_id <= transaction_id) \
            .filter(share_series_version.operation_type != 2) \
            .filter(share_series_version.share_class_id == share_class_id) \
            .filter(or_(share_series_version.end_transaction_id == None,  # pylint: disable=singleton-comparison # noqa: E711,E501;
                        share_series_version.end_transaction_id > transaction_id)) \
            .order_by(share_series_version.transaction_id).all()
        share_series_arr = []
        for share_series in share_series_list:
            share_series_json = VersionedBusinessDetailsService.share_series_revision_json(share_series)
            share_series_json['type'] = 'Series'
            share_series_json['id'] = str(share_series_json['id'])
            share_series_arr.append(share_series_json)
        return share_series_arr

    @staticmethod
    def get_name_translations_revision(transaction_id, legal_entity_id) -> dict:
        """Consolidates all name translations upto the given transaction id."""
        name_translations_version = version_class(Alias)
        name_translations_list = db.session.query(name_translations_version) \
            .filter(name_translations_version.transaction_id <= transaction_id) \
            .filter(name_translations_version.operation_type != 2) \
            .filter(name_translations_version.legal_entity_id == legal_entity_id) \
            .filter(name_translations_version.type == 'TRANSLATION') \
            .filter(or_(name_translations_version.end_transaction_id == None,  # pylint: disable=singleton-comparison # noqa: E711,E501;
                        name_translations_version.end_transaction_id > transaction_id)) \
            .order_by(name_translations_version.transaction_id).all()
        name_translations_arr = []
        for name_translation in name_translations_list:
            name_translation_json = VersionedBusinessDetailsService.name_translations_json(name_translation)
            name_translations_arr.append(name_translation_json)
        return name_translations_arr

    @staticmethod
    def get_name_translations_before_revision(transaction_id, legal_entity_id) -> dict:
        """Consolidates all name translations before deletion given a transaction id."""
        name_translations_version = version_class(Alias)
        name_translations_list = db.session.query(name_translations_version) \
            .filter(name_translations_version.transaction_id <= transaction_id) \
            .filter(name_translations_version.operation_type != 2) \
            .filter(name_translations_version.legal_entity_id == legal_entity_id) \
            .filter(name_translations_version.type == 'TRANSLATION') \
            .order_by(name_translations_version.transaction_id).all()
        name_translations_arr = []
        for name_translation in name_translations_list:
            name_translation_json = VersionedBusinessDetailsService.name_translations_json(name_translation)
            name_translations_arr.append(name_translation_json)
        return name_translations_arr

    @staticmethod
    def get_resolution_dates_revision(transaction_id, legal_entity_id) -> dict:
        """Consolidates all resolutions upto the given transaction id."""
        resolution_version = version_class(Resolution)
        resolution_list = db.session.query(resolution_version) \
            .filter(resolution_version.transaction_id <= transaction_id) \
            .filter(resolution_version.operation_type != 2) \
            .filter(resolution_version.legal_entity_id == legal_entity_id) \
            .filter(resolution_version.resolution_type == 'SPECIAL') \
            .filter(or_(resolution_version.end_transaction_id == None,  # pylint: disable=singleton-comparison # noqa: E711,E501;
                        resolution_version.end_transaction_id > transaction_id)) \
            .order_by(resolution_version.transaction_id).all()
        resolutions_arr = []
        for resolution in resolution_list:
            resolution_json = VersionedBusinessDetailsService.resolution_json(resolution)
            resolutions_arr.append(resolution_json)
        return resolutions_arr

    @staticmethod
    def party_role_revision_json(transaction_id, party_role_revision, is_ia_or_after) -> dict:
        """Return the party member as a json object."""
        cessation_date = datetime.date(party_role_revision.cessation_date).isoformat() \
            if party_role_revision.cessation_date else None
        if party_role_revision.related_colin_entity_id:
            party_revision = \
                VersionedBusinessDetailsService.get_colin_entity_revision(transaction_id,
                                                                          party_role_revision.related_entity_id)
            party = VersionedBusinessDetailsService.colin_entity_revision_json(transaction_id,
                                                                               party_revision,
                                                                               is_ia_or_after)
        else:
            party_revision = VersionedBusinessDetailsService.get_party_revision(transaction_id,
                                                                                party_role_revision.related_entity_id)
            party = VersionedBusinessDetailsService.party_revision_json(transaction_id,
                                                                        party_revision,
                                                                        is_ia_or_after)

        if is_ia_or_after:
            party['roles'] = [{
                'appointmentDate': datetime.date(party_role_revision.appointment_date).isoformat(),
                'roleType': ' '.join(r.capitalize() for r in party_role_revision.role_type.name.split('_')),
                # This id is required to find diff
                'id': ' '.join(r.capitalize() for r in party_role_revision.role_type.name.split('_'))
            }]
        else:
            party.update({
                'appointmentDate': datetime.date(party_role_revision.appointment_date).isoformat(),
                'cessationDate': cessation_date,
                'role': party_role_revision.role_type.name
            })

        return party

    @staticmethod
    def get_party_revision(transaction_id, party_id) -> dict:
        """Consolidates all party changes upto the given transaction id."""
        party_version = version_class(LegalEntity)
        party = db.session.query(party_version) \
            .filter(party_version.transaction_id <= transaction_id) \
            .filter(party_version.operation_type != 2) \
            .filter(party_version.id == party_id) \
            .filter(or_(party_version.end_transaction_id == None,  # pylint: disable=singleton-comparison # noqa: E711,E501;
                        party_version.end_transaction_id > transaction_id)) \
            .order_by(party_version.transaction_id).one_or_none()
        return party

    @staticmethod
    def party_revision_type_json(party_revision, is_ia_or_after) -> dict:
        """Return the party member by type as a json object."""
        member = {}
        if party_revision.entity_type == LegalEntity.EntityTypes.PERSON.value:
            member = {
                'officer': {
                    'firstName': party_revision.first_name,
                    'lastName': party_revision.last_name,
                    'partyType': LegalEntity.EntityTypes.PERSON.value
                }
            }
            if party_revision.title:
                member['title'] = party_revision.title
            if party_revision.middle_initial:
                member['officer']['middleInitial'] = party_revision.middle_initial
                member['officer']['middleName' if is_ia_or_after else 'middleInitial'] = party_revision.middle_initial
        else:
            member = {
                'officer': {
                    'organizationName': party_revision.legal_name,
                    'partyType': LegalEntity.EntityTypes.ORGANIZATION.value,
                    'identifier': party_revision._identifier  # pylint: disable=protected-access
                }
            }
        if party_revision.email:
            member['email'] = party_revision.email
        return member

    @staticmethod
    def party_revision_json(transaction_id, party_revision, is_ia_or_after) -> dict:
        """Return the party member as a json object."""
        member = VersionedBusinessDetailsService.party_revision_type_json(party_revision, is_ia_or_after)
        if party_revision.delivery_address_id:
            address_revision = VersionedBusinessDetailsService.get_address_revision(
                transaction_id, party_revision.delivery_address_id)
            # This condition can be removed once we correct data in address and address_version table
            # by removing empty address entry.
            if address_revision and address_revision.postal_code:
                member_address = VersionedBusinessDetailsService.address_revision_json(address_revision)
                if 'addressType' in member_address:
                    del member_address['addressType']
                member['deliveryAddress'] = member_address
        if party_revision.mailing_address_id:
            member_mailing_address = \
                VersionedBusinessDetailsService.address_revision_json(
                    VersionedBusinessDetailsService.get_address_revision
                    (transaction_id, party_revision.mailing_address_id))
            if 'addressType' in member_mailing_address:
                del member_mailing_address['addressType']
            member['mailingAddress'] = member_mailing_address
        else:
            if party_revision.entity_delivery_address:
                member['mailingAddress'] = member['deliveryAddress']

        if is_ia_or_after:
            member['officer']['id'] = str(party_revision.id)

        member['id'] = str(party_revision.id)  # This is required to find diff

        return member

    @staticmethod
    def get_colin_entity_revision(transaction_id, party_id) -> dict:
        """Consolidates all party changes upto the given transaction id."""
        party_version = version_class(ColinEntity)
        party = db.session.query(party_version) \
            .filter(party_version.transaction_id <= transaction_id) \
            .filter(party_version.operation_type != 2) \
            .filter(party_version.id == party_id) \
            .filter(or_(party_version.end_transaction_id == None,  # pylint: disable=singleton-comparison # noqa: E711,E501;
                        party_version.end_transaction_id > transaction_id)) \
            .order_by(party_version.transaction_id).one_or_none()
        return party

    @staticmethod
    def colin_entity_revision_type_json(party_revision, is_ia_or_after) -> dict:
        """Return the party member by type as a json object."""
        member = {
            'officer': {
                'organizationName': party_revision.organization_name,
                'partyType': LegalEntity.EntityTypes.ORGANIZATION.value,
                'identifier': party_revision.identifier
            }
        }
        if party_revision.email:
            member['email'] = party_revision.email
        return member

    @staticmethod
    def colin_entity_revision_json(transaction_id, party_revision, is_ia_or_after) -> dict:
        """Return the party member as a json object."""
        member = VersionedBusinessDetailsService.colin_entity_revision_type_json(party_revision, is_ia_or_after)
        if party_revision.delivery_address_id:
            address_revision = VersionedBusinessDetailsService.get_address_revision(
                transaction_id, party_revision.delivery_address_id)
            # This condition can be removed once we correct data in address and address_version table
            # by removing empty address entry.
            if address_revision and address_revision.postal_code:
                member_address = VersionedBusinessDetailsService.address_revision_json(address_revision)
                if 'addressType' in member_address:
                    del member_address['addressType']
                member['deliveryAddress'] = member_address
        if party_revision.mailing_address_id:
            member_mailing_address = \
                VersionedBusinessDetailsService.address_revision_json(
                    VersionedBusinessDetailsService.get_address_revision
                    (transaction_id, party_revision.mailing_address_id))
            if 'addressType' in member_mailing_address:
                del member_mailing_address['addressType']
            member['mailingAddress'] = member_mailing_address
        else:
            if party_revision.entity_delivery_address:
                member['mailingAddress'] = member['deliveryAddress']

        if is_ia_or_after:
            member['officer']['id'] = str(party_revision.id)

        member['id'] = str(party_revision.id)  # This is required to find diff

        return member

    @staticmethod
    def get_address_revision(transaction_id, address_id) -> dict:
        """Consolidates all party changes upto the given transaction id."""
        address_version = version_class(Address)
        address = db.session.query(address_version) \
            .filter(address_version.transaction_id <= transaction_id) \
            .filter(address_version.operation_type != 2) \
            .filter(address_version.id == address_id) \
            .filter(or_(address_version.end_transaction_id == None,  # pylint: disable=singleton-comparison # noqa: E711,E501;
                        address_version.end_transaction_id > transaction_id)) \
            .order_by(address_version.transaction_id).one_or_none()
        return address

    @staticmethod
    def address_revision_json(address_revision):
        """Return a dict of this object, with keys in JSON format."""
        country_description = ''
        if address_revision.country:
            country_description = pycountry.countries.search_fuzzy(address_revision.country)[0].name
        return {
            'streetAddress': address_revision.street,
            'streetAddressAdditional': address_revision.street_additional or '',
            'addressType': address_revision.address_type,
            'addressCity': address_revision.city,
            'addressRegion': address_revision.region or '',
            'addressCountry': address_revision.country,
            'addressCountryDescription': country_description,
            'postalCode': address_revision.postal_code,
            'deliveryInstructions': address_revision.delivery_instructions or ''
        }

    @staticmethod
    def share_class_revision_json(share_class_revision) -> dict:
        """Return the share_class as a json object."""
        share_class = {
            'id': share_class_revision.id,
            'name': share_class_revision.name,
            'priority': share_class_revision.priority,
            'hasMaximumShares': share_class_revision.max_share_flag,
            'maxNumberOfShares': share_class_revision.max_shares,
            'hasParValue': share_class_revision.par_value_flag,
            'parValue': share_class_revision.par_value,
            'currency': share_class_revision.currency,
            'hasRightsOrRestrictions': share_class_revision.special_rights_flag
        }
        return share_class

    @staticmethod
    def share_series_revision_json(share_series_revision) -> dict:
        """Return the share series revision as a json object."""
        share_series = {
            'id': share_series_revision.id,
            'name': share_series_revision.name,
            'priority': share_series_revision.priority,
            'hasMaximumShares': share_series_revision.max_share_flag,
            'maxNumberOfShares': share_series_revision.max_shares,
            'hasRightsOrRestrictions': share_series_revision.special_rights_flag
        }
        return share_series

    @staticmethod
    def name_translations_json(name_translation_revision) -> dict:
        """Return the name translation revision as a json object."""
        name_translation = {
            'id': str(name_translation_revision.id),
            'name': name_translation_revision.alias,
            'type': name_translation_revision.type
        }
        return name_translation

    @staticmethod
    def resolution_json(resolution_revision) -> dict:
        """Return the resolution revision as a json object."""
        resolution = {
            'id': resolution_revision.id,
            'date': resolution_revision.resolution_date.strftime('%B %-d, %Y'),
            'type': resolution_revision.resolution_type
        }
        return resolution

    @staticmethod
    def business_revision_json(business_revision, business_json):
        """Return the business revision as a json object."""
        business_json['hasRestrictions'] = business_revision.restriction_ind
        business_json['dissolutionDate'] = LegislationDatetime.format_as_legislation_date(
            business_revision.dissolution_date) if business_revision.dissolution_date else None
        business_json['restorationExpiryDate'] = LegislationDatetime.format_as_legislation_date(
            business_revision.restoration_expiry_date) if business_revision.restoration_expiry_date else None
        business_json['startDate'] = LegislationDatetime.format_as_legislation_date(
            business_revision.start_date) if business_revision.start_date else None
        business_json['continuationOutDate'] = LegislationDatetime.format_as_legislation_date(
            business_revision.continuation_out_date) if business_revision.continuation_out_date else None

        if business_revision.tax_id:
            business_json['taxId'] = business_revision.tax_id
        business_json['legalName'] = business_revision.legal_name
        business_json['businessName'] = business_revision.business_name
        business_json['legalType'] = business_revision.entity_type
        business_json['naicsDescription'] = business_revision.naics_description
        return business_json

    @staticmethod
    def get_incorporation_agreement_json(filing):
        """Return incorporation agreement from filing json."""
        return filing.json['filing']['incorporationApplication'].get('incorporationAgreement', {})

    @staticmethod
    def get_name_request_revision(filing):
        """Return name request from filing json."""
        return filing.json['filing']['incorporationApplication'].get('nameRequest', {})

    @staticmethod
    def get_contact_point_revision(filing):
        """Return contact point from filing json."""
        return filing.json['filing']['incorporationApplication'].get('contactPoint', {})
