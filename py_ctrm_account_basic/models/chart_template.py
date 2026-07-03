# For copyright and license notices, see __manifest__.py file in module root

from odoo import models, api


class AccountChartTemplate(models.Model):
    _inherit = "account.chart.template"

    @api.model
    def _prepare_all_journals(
            self, acc_template_ref, company, journals_dict=None):
        """ ponemos usa documentos en false porque si lo ponemos en true no
            genera las secuencias, solo se generan cuando lo ponemos a mano.
        """

        journal_data = super()._prepare_all_journals(acc_template_ref, company,
                                                     journals_dict)

        # if chart has localization, then we use documents by default
#        if company._localization_use_documents():
#            for vals_journal in journal_data:
#                if vals_journal['type'] in ['sale', 'purchase']:
#                    vals_journal['l10n_latam_use_documents'] = False
        return journal_data
