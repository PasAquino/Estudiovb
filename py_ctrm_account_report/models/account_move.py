from odoo import fields, models, exceptions, api
from datetime import datetime, timedelta
from odoo.exceptions import ValidationError


class Asientos(models.Model):
    _inherit = 'account.move'
    '''
        recibe como parametro en el context el valor del campo name para notas de REMISION
    '''

    num_asiento = fields.Integer(string='Numero de asiento')
    concepto_asiento = fields.Char(size=70, required=False, string="Concepto")

    # def post(self):
    #     # pdb.set_trace()
    #     res = super(Asientos, self).post()
    #     asd =0
    #     fec=datetime.strptime(str(self.date), "%Y-%m-%d")
    #     ye=fec.year
    #     #fecha = datetime.date(self.date)
    #     #ano = ye.year
    #     #raise ValidationError('asdaa %s' % ye)
    #
    #     fecha_start = str (ye) + '-01-01'
    #     # codes = [journal.code for journal in
    #     #          self.env['account.journal'].search([('id', 'in', data['form']['journal_ids'])])]
    #     asientos = self.env['account.move'].search_count([('date','>=',fecha_start)])
    #     secuencia = self.env['ir.sequence'].search([('code','=','asiento.sequence')])
    #
    #     # raise ValidationError ('codigo sec %s , asientos %s' % (secuencia.code, asientos) )
    #     if asientos <= 1:
    #         secuencia.write({'number_next_actual':1})
    #
    #
    #     if res:
    #         sequence_obj = self.env['ir.sequence']
    #
    #         numero_asiento = sequence_obj.get('asiento.sequence')
    #         self.write({'num_asiento': int(numero_asiento)})
    #
    #     #self.renumerar_asientos()
    #     return res

    @api.model
    def renumerar_asientos(self, periodo, company_id):
        ## EL CAMPO FECHA DEBE SER LA FECHA DE INICIO DE BUSQUEDA YA QUE LUEGO YO LE SACO EL ANHO PARA PODER CONCATENAR CON LA FECHA DE INICIO DEL ANHO Y LA FECHA FINAL DEL ANHO, ASI QUE ES IMPORTANTE QUE LE PONGAS
        # fecha = datetime.strptime(self.date, "%Y-%m-%d")
        empresa = company_id
        anio = periodo
        fecha_start = str(anio) + '-01-01'
        fecha_fin = str(anio) + '-12-31'
        fecha_start = "'" + fecha_start + "'"
        fecha_fin = "'" + fecha_fin + "'"
        cr = self._cr
        cr.execute(
            'select id, date '
            'from account_move '
            'where date >= %s '
            'and date <= %s '
            'and state = %s '
            'and company_id = %s '
            'order by date, id' % (
                fecha_start, fecha_fin, "'posted'", empresa))
        asientos = cr.fetchall()
        secuencia = 1
        for asi in asientos:
            asiento = self.env['account.move'].search([('id', '=', asi[0])])

            asiento.write({'num_asiento': secuencia})
            secuencia += 1
