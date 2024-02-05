# Copyright © 2020 Province of British Columbia
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
"""This module holds data for role addresses."""
from __future__ import annotations

from sql_versioning import Versioned

from .db import db
from .entity_role import EntityRole


class RoleAddress(Versioned, db.Model):
    """This class manages the role addresses."""

    __tablename__ = "role_addresses"
    __mapper_args__ = {
        "include_properties": [
            "id",
            "change_filing_id",
            "delivery_address_id",
            "legal_entity_id",
            "mailing_address_id",
            "role_type",
        ]
    }

    id = db.Column(db.Integer, primary_key=True)
    role_type = db.Column("role_type", db.Enum(EntityRole.RoleTypes), nullable=False)

    # parent keys
    change_filing_id = db.Column("change_filing_id", db.Integer, db.ForeignKey("filings.id"), index=True)
    legal_entity_id = db.Column("legal_entity_id", db.Integer, db.ForeignKey("legal_entities.id"))
    delivery_address_id = db.Column("delivery_address_id", db.Integer, db.ForeignKey("addresses.id"))
    mailing_address_id = db.Column("mailing_address_id", db.Integer, db.ForeignKey("addresses.id"))

    # relationships
    delivery_address = db.relationship("Address", foreign_keys=[delivery_address_id])
    mailing_address = db.relationship("Address", foreign_keys=[mailing_address_id])

    def save(self):
        """Save the object to the database immediately."""
        db.session.add(self)
        db.session.commit()
