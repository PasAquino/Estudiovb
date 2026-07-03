# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import tools, models, fields


class AccountBalance(models.Model):
    """ Base model for new Paraguayan VAT reports.
    The idea is that this lines have all the necessary data and which any
    changes in odoo, this ones will be taken for this cube and then no changes
    will be nedeed in the reports that use this lines.
    A line is created for each accounting entry that is affected by VAT tax.

    Basically which it does is cover the accounting entries into columns
    depending of the information of the taxes and add some other fields
    """

    _name = "account.balance.new"
    _description = "VAT line for Analysis in Paraguayan Localization"
    _auto = False

    cuentas = fields.Char(
        readonly=True, string='Cuenta'
    )
    montos = fields.Float(
        readonly=True, string='Monto'
    )

    def open_journal_entry(self):
        self.ensure_one()
        return self.move_id.get_formview_action()

    def init(self):
        cr = self._cr
        tools.drop_view_if_exists(cr, self._table)
        # we use tax_ids for base amount instead of tax_base_amount for two
        # reasons:
        # * zero taxes do not create any aml line so we can't get base for
        #   them with tax_base_amount
        # * we use same method as in odoo tax report to avoid any possible
        #   discrepancy with the computed tax_base_amount
        query = """
            select 'ACTIVO' Activo, sum(line.balance) as total
            from account_account as account
            left join account_move_line as line on line.account_id = account.id
            where account.company_id = 1 
            and account.code ilike ('1%')
            Union
            select 'PASIVO' Pasivo, sum(line.balance) as total 
            from account_account as account
            left join account_move_line as line on line.account_id = account.id
            where account.company_id = 1 
            and account.code ilike ('2%')
            Union
            select 'INGRESOS' Ingresos, sum(line.balance) as total 
            from account_account as account
            left join account_move_line as line on line.account_id = account.id
            where account.company_id = 1 
            and account.code ilike ('3%')
            Union
            select 'EGRESOS' Egresos, sum(line.balance) as total 
            from account_account as account
            left join account_move_line as line on line.account_id = account.id
            where account.company_id = 1 
            and account.code ilike ('4%')
            Union
            select 'Perdidas y Ganancias' PerdidasyGanancias, sum(line.balance) as total 
            from account_account as account
            left join account_move_line as line on line.account_id = account.id
            where account.company_id = 1 
            and account.code ilike ('9%')
"""
        sql = """CREATE or REPLACE VIEW %s as (%s)""" % (self._table, query)
        cr.execute(sql)
