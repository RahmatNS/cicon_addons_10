from odoo import models, fields, api
from odoo.exceptions import UserError

class CmmsJobOrderStatusWizard(models.TransientModel):
    _name = 'cmms.job.order.status.wizard'
    _description = "Job order status wizard "

    status_id = fields.Many2one('cmms.job.order.status', string="Job order Status", required=True)

    @api.multi
    def change_status(self):
        self.ensure_one()
        if self._context.get('job_order_ids', False):
            _job_orders = self.env['cmms.job.order'].search([('id', 'in', self._context.get('job_order_ids')), ('job_order_type','=', 'preventive')])
            if _job_orders and self.status_id.state_name == 'cancel' and self.env['cmms.store.invoice.line'].search_count([('job_order_id', '=', _job_orders._ids)]) > 0:
                raise UserError ('Cannot change Status of job order with Spare Parts')
            else:
                _job_orders.write({'status_id': self.status_id.id})
        return True

