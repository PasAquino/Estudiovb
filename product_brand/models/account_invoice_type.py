# Copyright 2018 Tecnativa - David Vidal
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, fields, models


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    product_type_id = fields.Many2one(comodel_name="product.type", string="Tipo")

    @api.model
    def _select(self):
        select_str = super(AccountInvoiceReport, self)._select()
        select_str += """
                , template.product_type_id as product_type_id
                """
        return select_str

    @api.model
    def _group_by(self):
        group_by_str = super(AccountInvoiceReport, self)._group_by()
        group_by_str += ", template.product_type_id"
        return group_by_str
