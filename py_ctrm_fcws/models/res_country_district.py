from odoo import api, fields, models


class ResDistrict(models.Model):
    _name = "res.country.district"
    _description = "District"
    _order = "name"
    _rec_names_search = ["name", "code"]

    name = fields.Char(
        string="Name",
        required=True,
        translate=True,
        help="Name or description of the district.",
    )
    code = fields.Char(
        string="Code", required=True, help="Unique code identifying the district."
    )
    state_id = fields.Many2one(
        "res.country.state",
        string="State",
        required=True,
        help="State (department) to which this district belongs.",
    )
    city_ids = fields.One2many(
        "res.city",
        "district_id",
        string="Cities",
        help="Cities that belong to this district.",
    )

    @api.depends("code")
    def _compute_display_name(self):
        for district in self:
            name = (
                district.name
                if not district.code
                else f"{district.name} ({district.code})"
            )
            district.display_name = name
