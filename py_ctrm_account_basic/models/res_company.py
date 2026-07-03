# For copyright and license notices, see __manifest__.py file in module root

from odoo import models


class ResCompany(models.Model):
    _inherit = "res.company"

    def _localization_use_documents(self):
        self.ensure_one()
        return True
