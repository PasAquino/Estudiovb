import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResCountry(models.Model):
    _inherit = "res.country"

    sifen_code = fields.Char(
        string="Código país SIFEN",
        size=3,
        help="Código ISO 3166-1 alfa-3 utilizado por SIFEN.",
    )

    @api.constrains("sifen_code")
    def _check_sifen_code(self):
        for country in self.filtered("sifen_code"):
            code = country.sifen_code.strip().upper()
            if not re.match(r"^[A-Z]{3}$", code):
                raise ValidationError(
                    "El Código país SIFEN debe tener exactamente tres letras."
                )
            if country.sifen_code != code:
                country.sifen_code = code
