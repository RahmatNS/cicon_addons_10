from odoo import fields,models,api
import xlsxwriter
import cStringIO
import base64
from datetime import datetime,date,timedelta


_machines = None
_inv_lines = None
_calender = ['January', 'February', 'March', 'April' , 'May' ,'June' ,'July', 'August', 'September', 'October', 'November', 'December']

class ReportMachineAnalysisSummary(models.AbstractModel): # Report File Name
    _name = 'report.cmms.report_machine_analysis_summary_template'

    @api.model
    def render_html(self,docids, data=None):
        data = data if data is not None else {}
        report_obj = self.env['report']
        report = report_obj._get_report_from_name('cmms.report_machine_analysis_summary_template')
        _docs = self._get_report_data(data.get('ids', data.get('active_ids')))

        docargs = {
            'doc_ids': data.get('ids', data.get('active_ids')),
            'doc_model': report.model,
            'docs': _docs,
            'heading': self._context.get('heading'),
            'year' : self._context.get('year'),
            'get_category': self._get_categories,
            'get_machine': self._get_machines,
            'get_breakdown_count': self._job_order_count,
            'get_months': _calender
        }
        self._create_xls()
        return report_obj.render('cmms.report_machine_analysis_summary_template', docargs)

    def _create_xls(self):
        output = cStringIO.StringIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        format1 = workbook.add_format()
        format1.set_num_format('###0.00')
        worksheet = workbook.add_worksheet("Machine")
        row = 0
        col = 5
        worksheet.write(row, 0, 'Sn#')
        worksheet.write(row, 1, 'TYPE')
        worksheet.write(row, 2, 'CATEGORY')
        worksheet.write(row, 3, 'CODE')
        worksheet.write(row, 4, 'NAME')
        worksheet.write(row, 5, 'DESCRIPTION')
        for _mn in _calender:
            col += 1
            worksheet.write(row, col, _mn)
        worksheet.write(row, 18, 'TOTAL')
        for _mType in self._get_report_data(None):
            for _mCateg in self._get_categories(_mType):
                for _macs in self._get_machines(_mType , _mCateg):
                    _mac = _macs.get('machine_id')
                    row += 1
                    col = 5
                    worksheet.write(row, 0, row)
                    worksheet.write(row, 1, _mac.type_id.name)
                    worksheet.write(row, 2, _mac.category_id.name)
                    worksheet.write(row, 3, _mac.code)
                    worksheet.write(row, 4, _mac.name)
                    worksheet.write(row, 5, 'EXPENSE')
                    for _mn in _calender:
                        col += 1
                        worksheet.write(row, col, _macs.get(_mn))
                    worksheet.write_formula(row, 18, '=SUM(G' + str(row) + ':' + 'R' + str(row) + ')')
        workbook.close()
        output.seek(0)
        _r_name = 'Machine Analysis -' + datetime.today().strftime('%d-%b-%Y')
        _file_name = 'machine_analysis_' + datetime.today().strftime('%d-%b-%Y') + '.xlsx'
        vals = {
            'name': _r_name,
            'datas_fname': _file_name,
            'description': 'Machine Analysis',
            'type': 'binary',
            'db_datas': base64.encodestring(output.read()),
            'res_name': "Machine Analysis",
            'res_model': 'cmms.common.report.wizard',
            'res_id': self._context.get('active_id')
        }
        file_id = self.env['ir.attachment'].create(vals)

    def _get_report_data(self,data):
        _qry =[]
        if self._context.get('company_id'):
            _qry.append(('company_id','=',self._context.get('company_id')))
        if self._context.get('machine_categ_ids'):
            _qry.append(('category_id', 'in', self._context.get('machine_categ_ids')))
        if self._context.get('machine_type_ids'):
            _qry.append(('type_id', 'in', self._context.get('machine_type_ids')))
        self._machines = self.env['cmms.machine'].search(_qry)
        _types = self._machines.mapped('type_id').sorted(lambda t: t.name)
        return _types

    def _get_time_diff_min(self, _startTime, _endTime):
        _start = fields.Datetime.from_string(_startTime)
        _end = fields.Datetime.from_string(_endTime)
        _diff = _end - _start
        return (_diff.days, (_diff.seconds / 60))

    def _job_order_count(self, _mid):
        year = self._context.get('year')
        _start_date = self._context.get('from_date')
        _end_date = self._context.get('to_date')

        breakdown_dict = {}
        _breakdown_entry = {}
        _idle_time_dict = {}
        _res = self.env['cmms.job.order'].read_group(domain=[('job_order_date', '>=',_start_date),('job_order_date', '<=', _end_date),('machine_id', '=', _mid),('job_order_type','=','breakdown')],
                                                     fields=['job_order_date','job_order_type'], groupby=[('job_order_date:month'),('job_order_type')])
        _job_orders = self.env['cmms.job.order'].search(
            [('machine_id', '=', _mid), '|', '&', ('job_order_date', '>=', _start_date),
             ('job_order_date', '<=', _end_date),
             ('completed_date', '>=', _start_date), ('completed_date', '<=', _end_date),
             ('job_order_type', 'in', ('breakdown', 'preventive'))])

        for r in _res:
            _breakdown_entry[r['job_order_date:month'].replace(year,'').strip()] = r['job_order_date_count']
            _job_orders_on_month = _job_orders.filtered(lambda a: fields.Date.from_string(a.job_order_date).strftime('%B %Y') == r['job_order_date:month'])
            for _job in _job_orders_on_month:
                _idle_mins = []
                if _job.job_order_type == 'breakdown':
                    _idle_mins.append(self._get_time_diff_min(_job.breakdown_datetime, _job.work_end_datetime))
                elif _job.job_order_type == 'preventive':
                    _idle_mins.append(self._get_time_diff_min(_job.work_start_datetime, _job.work_end_datetime))
            _idle_time_dict[r['job_order_date:month'].replace(year, '').strip()] = (sum([m[0] for m in _idle_mins]), str((sum([m[1] for m in _idle_mins])/60)).zfill(2) + ':' +  str(sum([m[1] for m in _idle_mins]) % 60).zfill(2))
        breakdown_dict.update(idle_time=_idle_time_dict)
        _total_jobOrder = sum(_breakdown_entry.values())
        if _total_jobOrder > 0:
            _breakdown_entry['total_job_order'] = _total_jobOrder
        else:
            _breakdown_entry['total_job_order'] = ''
        breakdown_dict.update(breakdown_count=_breakdown_entry)
        return breakdown_dict

    def _get_categories(self, _type):
        _categs = self._machines.filtered(lambda r: r.type_id == _type).mapped('category_id').sorted(lambda c: c.name)
        return _categs

    def _get_machines(self, _type, _categ):
        year = self._context.get('year')
        _start_date = self._context.get('from_date')
        _end_date = self._context.get('to_date')
        _machine_list = []
        _machines = self._machines.filtered(lambda r: r.category_id == _categ and r.type_id == _type).sorted(key=lambda r: r.set_code)

        for _mac in _machines.sorted(lambda a:a.code):
            _machine_entry = {}
            month_wise = self.env['cmms.store.invoice.line'].read_group(domain=[('invoice_date', '>=',_start_date),('invoice_date', '<=', _end_date),('machine_id', '=',_mac.id)],
                                                                                fields=['invoice_date','machine_id','amount'],
                                                                                groupby=[('invoice_date:month'),('machine_id')])
            #print month_wise
            for _res in month_wise:
                _machine_entry[_res['invoice_date:month'].replace(year,'').strip()] = round(_res['amount'],2)
            _total_expense = sum(_machine_entry.values())
            for _res in month_wise:
                _machine_entry[_res['invoice_date:month'].replace(year,'').strip()] = "{:.2f}".format(round(_res['amount'],2))
            if _total_expense > 0:
                _machine_entry['total_expense'] = "{:.2f}".format(round(_total_expense, 2))
            else:
                _machine_entry['total_expense'] = ''
            _machine_entry.update(machine_id=_mac)
            _machine_list.append(_machine_entry)


        return _machine_list
