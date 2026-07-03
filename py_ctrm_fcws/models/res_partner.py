import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

OPERATION_TYPE_SELECTION = [
    ("B2B", "Business to Business"),
    ("B2C", "Business to Consumer"),
    ("B2G", "Business to Government"),
    ("B2F", "Business to Foreign"),
]


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_py_operation_type = fields.Selection(
        selection=OPERATION_TYPE_SELECTION,
        string="Operation Type",
        help="Classification of the type of fiscal operation for SIFEN: "
        "B2B (Business to Business), B2C (Business to Consumer), "
        "B2G (Business to Government), B2F (Business to Foreign).",
    )

    def _get_l10n_py_operation_type(self):
        """Calculates the operation type for Paraguay based on ID type and country."""
        self.ensure_one()

        id_type = self.l10n_latam_identification_type_id
        country = self.country_id
        vat = self.vat or ""

        if not id_type:
            return False

        edi_code = id_type.edi_code

        # B2F: Foreign
        if edi_code in ("2", "3", "4") or (country and country.code != "PY"):
            return "B2F"

        # B2C: National ID, Anonymous, Passport, ID Card, etc.
        if edi_code in ("1", "5", "6", "9"):
            return "B2C"

        # B2B or B2G depending on RUC
        if id_type.is_vat:
            if self.is_company:
                # If RUC starts with 800, consider Government supplier
                if vat.startswith("800"):
                    return "B2G"
                return "B2B"
            else:
                return "B2C"

        return "B2C"

    def default_get(self, default_fields):
        vals = super().default_get(default_fields)
        if "country_id" not in vals:
            vals["country_id"] = self.env.company.country_id.id
        return vals

    @api.onchange("l10n_latam_identification_type_id")
    def _onchange_id_type_ctrm_l10n_py(self):
        """Assign fiscal position based on identification type."""
        if self.l10n_latam_identification_type_id.position_id:
            self.property_account_position_id = (
                self.l10n_latam_identification_type_id.position_id.id
            )

    def _check_ruc(self, ruc):
        """Validates that the RUC has the correct format and check digit."""
        if not ruc:
            return True
        if "-" not in ruc:
            return False
        numero, dv = ruc.split("-", 1)
        try:
            numero = int(numero)
            dv = int(dv)
        except ValueError:
            return False
        return dv == self._calc_dv(numero)

    @staticmethod
    def _calc_dv(ruc):
        """Calculates the check digit (DV) for a RUC number."""
        ruc_str = str(ruc)[::-1]
        v_total = 0
        basemax = 11
        k = 2
        for i in range(len(ruc_str)):
            if k > basemax:
                k = 2
            v_total += int(ruc_str[i]) * k
            k += 1
        resto = v_total % basemax
        return basemax - resto if resto > 1 else 0

    def check_vat_py(self, vat):
        """Validates format and check digit of Paraguayan RUC if it's a fiscal ID."""
        if vat == "XX":
            return True
        if self.l10n_latam_identification_type_id.is_vat:
            if len(vat.split("-")) != 2:
                return False
            pattern = r"^[0-9]{5,9}-[0-9]$"
            if not re.match(pattern, vat):
                return False
            return self._check_ruc(vat)
        return True

    @api.constrains("vat")
    def _check_vat_format(self):
        """Validates VAT format and check digit when saving the partner."""
        for record in self:
            if record.vat and not record.check_vat_py(record.vat):
                raise ValidationError(
                    _("The entered RUC number has an invalid format or check digit.")
                )

    @api.model_create_multi
    def create(self, vals):
        """Automatically assigns CI type and operation type if not defined."""
        ci_type = self.env.ref("py_ctrm_fcws.it_ci").id

        for idx, record in enumerate(vals):
            # Detect identification type
            partner_type = self.env["l10n_latam.identification.type"].browse(
                record.get("l10n_latam_identification_type_id", False)
            )
            partner_vat = record.get("vat", "")

            # Assign CI type if no hyphen and not a RUC
            if partner_vat:
                if partner_type and (
                    partner_type.is_vat or partner_type.rg_code != "1"
                ):
                    pass
                elif "-" not in partner_vat:
                    vals[idx]["l10n_latam_identification_type_id"] = ci_type

            # Calculate operation type if not defined manually
            if not record.get("l10n_py_operation_type"):
                temp_partner = self.new(record)
                vals[idx]["l10n_py_operation_type"] = (
                    temp_partner._get_l10n_py_operation_type()
                )

        return super().create(vals)

    @api.onchange("vat")
    def _onchange_vat_ctrm_l10n_py_edi(self):
        """Automatically assigns identification type based on VAT format."""
        if self.vat:
            vat_type = self.env.ref("py_ctrm_fcws.it_vat").id
            ci_type = self.env.ref("py_ctrm_fcws.it_ci").id
            if self.l10n_latam_identification_type_id.id in [vat_type, ci_type]:
                if "-" not in self.vat:
                    if self.l10n_latam_identification_type_id.id == vat_type:
                        self.l10n_latam_identification_type_id = ci_type
                else:
                    if self.l10n_latam_identification_type_id.id != vat_type:
                        self.l10n_latam_identification_type_id = vat_type
        # Update operation type
        self.l10n_py_operation_type = self._get_l10n_py_operation_type()
