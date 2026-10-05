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

SIFEN_CONSTANCIA_TYPE_SELECTION = [
    ("1", "Constancia de no ser contribuyente"),
    ("2", "Constancia de microproductores"),
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
    sifen_has_constancia = fields.Boolean(
        string="Tiene constancia SIFEN",
        help="Activar si el contacto posee una constancia válida para autofactura electrónica.",
    )
    sifen_constancia_type = fields.Selection(
        SIFEN_CONSTANCIA_TYPE_SELECTION,
        string="Tipo de constancia SIFEN",
    )
    sifen_constancia_number = fields.Char(
        string="Número de constancia",
        size=11,
    )
    sifen_constancia_control = fields.Char(
        string="Número de control",
        size=8,
    )
    sifen_constancia_date_start = fields.Date(string="Fecha de inicio")
    sifen_constancia_date_end = fields.Date(string="Fecha de fin")

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

    @api.constrains(
        "sifen_has_constancia",
        "sifen_constancia_type",
        "sifen_constancia_number",
        "sifen_constancia_control",
        "sifen_constancia_date_start",
        "sifen_constancia_date_end",
    )
    def _check_sifen_constancia(self):
        for partner in self:
            if partner.sifen_has_constancia:
                missing = []
                if not partner.sifen_constancia_type:
                    missing.append(_("Tipo de constancia SIFEN"))
                if not partner.sifen_constancia_number:
                    missing.append(_("Número de constancia"))
                if not partner.sifen_constancia_control:
                    missing.append(_("Número de control"))
                if not partner.sifen_constancia_date_start:
                    missing.append(_("Fecha de inicio"))
                if missing:
                    raise ValidationError(
                        _("Faltan datos de la constancia SIFEN:\n- %s")
                        % "\n- ".join(missing)
                    )
            if partner.sifen_constancia_number and (
                len(partner.sifen_constancia_number) != 11
                or not partner.sifen_constancia_number.isdigit()
            ):
                raise ValidationError(
                    _("El número de constancia SIFEN debe tener exactamente 11 dígitos.")
                )
            if partner.sifen_constancia_control and (
                len(partner.sifen_constancia_control) != 8
                or not partner.sifen_constancia_control.isalnum()
            ):
                raise ValidationError(
                    _("El número de control SIFEN debe tener 8 caracteres alfanuméricos.")
                )
            if (
                partner.sifen_constancia_date_end
                and partner.sifen_constancia_date_start
                and partner.sifen_constancia_date_end
                < partner.sifen_constancia_date_start
            ):
                raise ValidationError(
                    _("La fecha final de la constancia no puede ser anterior a la inicial.")
                )

    def _normalize_sifen_constancia_vals(self, vals):
        if vals.get("sifen_constancia_number"):
            vals["sifen_constancia_number"] = vals[
                "sifen_constancia_number"
            ].strip()
        if vals.get("sifen_constancia_control"):
            vals["sifen_constancia_control"] = vals[
                "sifen_constancia_control"
            ].strip().upper()
        return vals

    @api.model_create_multi
    def create(self, vals):
        """Automatically assigns CI type and operation type if not defined."""
        ci_type = self.env.ref("py_ctrm_fcws.it_ci").id

        for idx, record in enumerate(vals):
            self._normalize_sifen_constancia_vals(record)
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

    def write(self, vals):
        return super().write(self._normalize_sifen_constancia_vals(vals))

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
