from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime


class AccountCheckbooksDeposit(models.Model):
    _name = "account.checkbooks.deposit"
    _description = "Deposito de Cheques"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "deposit_date desc, name desc"

    @api.depends('company_id', 'currency_id', 'check_payment_ids', 'move_id.line_ids.reconciled')
    def _compute_check_deposit(self):
        for deposit in self:
            total = 0.0
            count = 0
            reconcile = False
            currency_none_same_company_id = False
            if deposit.company_id.currency_id != deposit.currency_id:
                currency_none_same_company_id = deposit.currency_id.id
            if deposit.company_id.currency_id == deposit.currency_id:
                currency_none_same_company_id = deposit.currency_id.id
            for line in deposit.check_payment_ids:
                count += 1
                if currency_none_same_company_id:
                    total += line.amount_payment
                else:
                    total += line.amount_payment
            if deposit.move_id:
                for line in deposit.move_id.line_ids:
                    if line.debit > 0 and line.reconciled:
                        reconcile = True
            deposit.total_amount = total
            deposit.is_reconcile = reconcile
            deposit.currency_none_same_company_id = currency_none_same_company_id
            deposit.check_count = count

    name = fields.Char(string="Name", size=64, readonly=True, default="Nuevo Deposito", tracking=True)
    deposit_date = fields.Date(string="Fecha Deposito", required=True, default=fields.Date.context_today, tracking=True)
    journal_id = fields.Many2one('account.journal', string="Diario", required=True, tracking=True,
                                 domain=[('type', '=', 'bank'), ('bank_account_id', '=', False), ('diario_de_cheques', '=', True)])
    journal_account_id = fields.Many2one('account.account', string="Cuenta Débito del Diario")
    bank_journal_id = fields.Many2one('account.journal', string="Cuenta Bancaria", required=True, tracking=True,
                                      domain="[('company_id', '=', company_id), ('type', '=', 'bank')]")
    bank_check_account_id = fields.Many2one('account.account', string="Cuenta Débito del Banco")
    state = fields.Selection(selection=[('draft', 'Borrador'), ('done', 'Confirmado'), ('cancel', 'Revertido')],
                             string='Estado', default='draft', readonly=True, tracking=True)
    move_id = fields.Many2one('account.move', string="Journal Entry", readonly=True)
    check_payment_ids = fields.One2many('payment.methods.group', 'check_deposit_id', string="Listado de Cheques")
    company_id = fields.Many2one('res.company', string="Empresa", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string="Moneda", required=True)
    currency_none_same_company_id = fields.Many2one('res.currency', compute="_compute_check_deposit", store=True,
                                                    string="Moneda (Falso si es igual que la empresa)")
    total_amount = fields.Monetary(compute="_compute_check_deposit", string="Monto Total", readonly=True, store=True, digits="Account", tracking=True)
    check_count = fields.Integer(compute="_compute_check_deposit", readonly=True, store=True, string="Cantidad de Cheques", tracking=True)
    is_reconcile = fields.Boolean(compute="_compute_check_deposit", readonly=True, store=True, string="Reconcile")
    nro_boleta = fields.Char(string="Boleta de Deposito", tracking=True)
    obs_cancel = fields.Char('Detalle por la Reversión')

    @api.model
    def create(self, vals):
        if vals.get("name", "Nuevo Deposito") == "Nuevo Deposito":
            vals["name"] = self.env['ir.sequence'].next_by_code('account.checkbooks.deposit') or _('Nuevo Deposito')
        return super(AccountCheckbooksDeposit, self).create(vals)

    @api.onchange('journal_id')
    def onchange_journal_id(self):
        for dep in self:
            if dep.journal_id:
                if dep.journal_id.currency_id:
                    dep.currency_id = dep.journal_id.currency_id
                else:
                    dep.currency_id = dep.journal_id.company_id.currency_id
                for account in dep.journal_id.inbound_payment_method_line_ids:
                    dep.journal_account_id = account.payment_account_id

    @api.onchange('bank_journal_id')
    def onchange_bank_journal_id(self):
        for dep in self:
            if dep.bank_journal_id:
                for account in dep.bank_journal_id.inbound_payment_method_line_ids:
                    dep.bank_check_account_id = account.payment_account_id

    def validate_deposit(self):
        if self.check_payment_ids:
            return self.validate_deposit_dep()
        else:
            raise ValidationError(_("No tiene linea de cheque para depositar"))

    @api.model
    def _prepare_account_move_vals(self, deposit):
        if deposit.company_id.check_deposit_offsetting_account == 'bank_account':
            journal_id = deposit.bank_journal_id.id
        else:
            journal_id = deposit.journal_id.id
        move_vals = {"journal_id": journal_id,
                     "date": deposit.deposit_date,
                     "ref": _("Deposito de Cheque: %s,- Boleta: %s") % (deposit.name, deposit.nro_boleta)}
        return move_vals

    @api.model
    def _prepare_move_line_vals(self, line, deposit):
        assert line.amount_payment > 0, "El débito debe tener un valor"
        return {"name": _("Deposito de Cheque - %s, - Ref. %s") % (line.bank_id.name, line.detalle_cheque),
                "partner_id": line.partner_id.id,
                "credit": line.amount_payment,
                "debit": 0.0,
                "account_id": deposit.journal_account_id.id,
                "currency_id": line.currency_id.id or False,
                "amount_currency": line.amount_payment * -1}

    @api.model
    def _prepare_counterpart_move_lines_vals(self, deposit, total_debit, total_amount_currency):
        company = deposit.company_id
        account_id = ""
        if not company.check_deposit_offsetting_account:
            raise UserError(_("Debe configurar la 'Cuenta de compensación de depósito de cheques' "
                              "en la página Configuración de contabilidad"))
        if company.check_deposit_offsetting_account == "bank_account":
            if not deposit.bank_check_account_id:
                raise UserError(_("Falta la 'cuenta de débito predeterminada' en el diario del banco '%s'") % deposit.bank_journal_id.name)
            account_id = deposit.bank_check_account_id.id
        elif company.check_deposit_offsetting_account == "transfer_account":
            if not company.check_deposit_transfer_account_id:
                raise UserError(_("Missing 'Check Deposit Offsetting Account' on the company '%s'.") % company.name)
            account_id = company.check_deposit_transfer_account_id.id
        return {
            "name": _("Deposito de Cheque: %s,- Boleta: %s") % (deposit.name, deposit.nro_boleta),
            "debit": total_debit,
            "credit": 0.0,
            "account_id": account_id,
            "partner_id": False,
            "currency_id": deposit.currency_id.id or False,
            "amount_currency": total_amount_currency,
        }

    def validate_deposit_dep(self):
        am_obj = self.env["account.move"]
        move_line_obj = self.env["account.move.line"]
        for deposit in self:
            move_vals = self._prepare_account_move_vals(deposit)
            move = am_obj.create(move_vals)
            total_debit = 0.0
            total_amount_currency = 0.0
            to_reconcile_lines = []
            for line in deposit.check_payment_ids:
                total_debit += line.amount_payment
                total_amount_currency += line.amount_payment
                line_vals = self._prepare_move_line_vals(line, deposit)
                line_vals['move_id'] = move.id
                move_line = move_line_obj.with_context(check_move_validity=False).create(line_vals)
                line.write({'state_check': 'deposited'})
                for eca in line.payment_group_id.payment_ids:
                    if eca.journal_id.id == deposit.journal_id.id:
                        for auxi in eca.move_id.line_ids:
                            if auxi.reconciled is False:
                                to_reconcile_lines.append(auxi + move_line)
            # Create counter-part
            counter_vals = self._prepare_counterpart_move_lines_vals(deposit, total_debit, total_amount_currency)
            counter_vals['move_id'] = move.id
            move_line_obj.create(counter_vals)
            if deposit.company_id.check_deposit_post_move:
                move.action_post()
            deposit.write({'state': 'done', 'move_id': move.id})
        return True

    @api.constrains("currency_id", "check_payment_ids", "company_id")
    def _check_deposit(self):
        for deposit in self:
            deposit_currency = deposit.currency_id
            if deposit_currency == deposit.company_id.currency_id:
                for line in deposit.check_payment_ids:
                    if line.currency_id != deposit_currency:
                        raise ValidationError(_("El cheque con monto %s y referencia '%s' "
                                                "está en la moneda %s pero el depósito está en "
                                                "moneda %s.") %
                                              (line.amount_payment, line.communication or "", line.currency_id.name, deposit_currency.name))
            else:
                for line in deposit.check_payment_ids:
                    if line.currency_id != deposit_currency:
                        raise ValidationError(_("El cheque con monto %s y referencia '%s' "
                                                "está en la moneda %s pero el depósito está en "
                                                "moneda %s.") %
                                              (line.amount_payment, line.communication or "", line.currency_id.name, deposit_currency.name))

    def action_cancel(self):
        for eca in self:
            eca.write({'state': 'cancel'})
            texto = ""
            for auxi in eca.check_payment_ids:
                total = '{0:,.2f}'.format(auxi.amount_payment).replace(',', 'a').replace('.', 'b').replace('a', '.').replace('b', ',')
                texto += 'Cliente: ' + auxi.partner_id.name + ' - Banco: ' + auxi.bank_id.name + ' - Fecha Emisión: ' + str(
                    auxi.fecha_cobro) + ' - Fecha Diferida: ' + str(auxi.fecha_diferida) + ' -\n N° Cheque: ' + str(
                    auxi.detalle_cheque) + ' - Monto: ' + str(total) + '\n'
            eca.obs_cancel = texto
            if eca.move_id:
                for ross in eca.move_id:
                    ross.write({'state': 'draft'})
                    for line in ross.line_ids:
                        line.write({'parent_state': 'draft'})
                eca.move_id.button_cancel()
            for dep in eca.check_payment_ids:
                dep.write({'check_deposit_id': False})
                dep.write({'state_check': 'to_deposit'})
            return {'effect': {'fadeout': 'slow', 'message': 'Deposito Revertido', 'type': 'rainbow_man'}}

    def action_draft(self):
        for deposit in self:
            if deposit.move_id:
                deposit.move_id.button_cancel()
                deposit.move_id.unlink()
            deposit.write({'state': 'draft'})
        return True

    def unlink(self):
        for deposit in self:
            if deposit.state == 'done':
                raise UserError(_("El depósito '%s' está en estado válido, por lo que debe cancelarlo antes de eliminarlo.") % deposit.name)
        return super(AccountCheckbooksDeposit, self).unlink()

    def action_print(self):
        report = self.env.ref("account_payment_paraguay.report_deposito_cheque_action")
        action = report.report_action(self)
        return action
