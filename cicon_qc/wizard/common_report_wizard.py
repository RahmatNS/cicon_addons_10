from odoo import models, fields, api


class QcCommonReportWizard(models.TransientModel):
    _name = 'qc.common.report.wizard'
    _description = "QC Reports"

    report_list = fields.Selection([('steel_approval_report', 'Steel Approval Report')],string='Report', required=True)
    option_select = fields.Selection([('include', 'Include'), ('exclude', 'Exclude')], string="Options",
                                     default='include', help='Include/Exclude records')
    origin_value_ids = fields.Many2many('product.attribute.value',
                                             domain="[('attribute_id.name','=','Steel Origin' )]", string='Origins')
    show_consultant = fields.Boolean('Show Consultant', default=False)
    hide_reject = fields.Boolean('Hide Rejected', default=False)
    show_filter = fields.Boolean('Filter Options', default=False)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.user.company_id)
    partner_id = fields.Many2one('res.partner', string='Partner')
    job_site_ids = fields.Many2many('cicon.job.site', string='Job Sites')

    @api.multi
    def show_report(self, data):
        self.ensure_one()
        ctx = dict(self._context)
        if self.company_id:
            ctx['company_id'] = self.company_id.id
        if self.report_list == 'steel_approval_report':
            ctx['heading'] = "Steel Approval Report"
            ctx['show_consultant'] = self.show_consultant
            ctx['hide_reject'] = self.hide_reject
            _qry = [('attribute_id.name','=','Steel Origin' )]
            if self.origin_value_ids:
                if self.option_select =='include':
                    _qry.append(('id', 'in', self.origin_value_ids._ids))
                elif self.option_select =='exclude':
                    _qry.append(('id', 'not in', self.origin_value_ids._ids))
            _origin_ids = self.env['product.attribute.value'].search(_qry)
            job_sites = []
            if self.show_filter:
                if self.partner_id and self.job_site_ids:
                    job_sites = self.with_context(ctx).job_site_ids
                if self.partner_id:
                    job_sites = self.with_context(ctx).env['cicon.job.site'].search[('partner_id', '=', self.partner_id.id)]
            else:
                job_sites = self.with_context(ctx).env['qc.material.approval'].search([]).mapped('job_site_id').filtered(lambda a: a.archive == False)
            _datas = {'origin_ids': _origin_ids._ids}
            return self.with_context(ctx).env['report'].get_action(job_sites, report_name='cicon_qc.qc_material_approval_report_template',data=_datas)

    @api.onchange('partner_id')
    def onchange_partner(self):
        if self.partner_id:
            self.job_site_ids = []
