# Copyright 2018 Tecnativa - David Vidal
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import fields, models


class SaleReport(models.Model):
    _inherit = "sale.report"

    product_type_id = fields.Many2one(comodel_name="product.type", string="Tipo")

    # pylint:disable=dangerous-default-value
    def _query(
            self, with_clause="", fields={}, groupby="", from_clause=""  # noqa: B006
    ):
        fields["product_type_id"] = ", t.product_type_id as product_type_id"
        groupby += ", t.product_type_id"
        return super(SaleReport, self)._query(with_clause, fields, groupby, from_clause)
