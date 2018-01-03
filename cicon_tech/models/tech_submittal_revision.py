from odoo import models, fields, api
from odoo.exceptions import UserError


class SumittalRevisionReason(models.Model):
    _name = 'tech.submittal.revision.reason'
    _description = "Revision Reason"

    name = fields.Char("Reason", required=True)

    _sql_constraints = [('unique_reason', 'unique(name)', ' Revision Reason Should be Unique')]

SumittalRevisionReason()


class SubmittalRevision(models.Model):
    """Submittal Revisions Information
        Note: Submittal_id inherited from tech.submittal using delegation inheritance
            Please refer : Inheritance and extension Section in ODOO Documentation
        mail.thread inherited for mail Chat integration
        Each revision refer to a mater submittal_id from tech.submittal, for revision # 0
        it created new submittal and after revision it just master submittal_id
         Please check notes on tech.submittal

         Note: All Fields use state check to if can edit or not State Explain it below

         state:
            'new': Draft State Editing allowed for all fields
            'approved': Readonly state for all fields Approved but not submitted
            'submitted': Readonly with document level revision allowed(Explained in Document Class) and enables
                        delivery information
            'resubmitted' : Super seeded state not visible on tree view
            'cancelled': Deleted revision goes this state as not real db delete performs here
    """
    _inherit = ['mail.thread']
    _name = 'tech.submittal.revision'
    _description = "Submittal Revision"
    _inherits = {'tech.submittal': 'submittal_id',
                 }
    _rec_name = 'ref_no'

    @api.multi
    @api.depends('delivery_ids', 'document_ids')
    def total_delivery(self):
        """ Computes delivery quantity , balance qty , drawing count and total_draft_time on change
         fields delivery_ids and document_ids
        """
        for rec in self:
            rec.delivered_qty = sum([d.delivered_qty for d in rec.delivery_ids])
            rec.balance_qty = rec.bbs_weight - rec.delivered_qty
            rec.dwg_count = len(rec.document_ids)
            rec.total_draft_time = sum(x.draft_time for x in rec.document_ids)
    # ParentId Store record Id which was revised
    parent_id = fields.Many2one('tech.submittal.revision', "Previous Revision", required=False)
    # Reference Auto Generated by function
    ref_no = fields.Char('Ref No', size=50, required=True, readonly=True, index=True,
                         states={'new': [('readonly', False)]})
    # Delegation Inherited Submittal Id :Refer Class Notes
    submittal_id = fields.Many2one('tech.submittal', 'Submittal', ondelete='cascade', required=True, readonly=True,
                                   states={'new': [('readonly', False)]}, index=True)
    submittal_date = fields.Date('Submittal Date', required=True, readonly=True,
                                 states={'new': [('readonly', False)]}, index=True, track_visibility='onchange', default=fields.Date.context_today)
    # Submitted By , Default by logged user can be change if required
    submitted_by = fields.Many2one('res.users', 'Submitted By', required=True, readonly=True,
                                   domain="[('login','!=','admin')]", states={'new': [('readonly', False)]},
                                   track_visibility='onchange', index=True,
                                   default=lambda self: self.env.user)
    # Revision number Generate by function +1
    revision_number = fields.Integer('Revision No', required=True, readonly=True,
                                     states={'new': [('readonly', False)]})
    bbs_weight = fields.Float('BBS Weight', required=True, track_visibility='onchange', readonly=True, states={'new': [('readonly', False)]})
    subject = fields.Char('Subject', required=True, index=True, readonly=True, states={'new': [('readonly', False)]})
    enclosures = fields.Text('Enclosure', readonly=True, states={'new': [('readonly', False)]})
    job_site_contact = fields.Many2one('tech.project.contact', "Project Contact", readonly=True,
                                       states={'new': [('readonly', False)]})
    # Manager user to whom Submitted by allowed to use
    signed_by = fields.Many2one('res.users', 'Signed By', required=True,
                                readonly=True, states={'new': [('readonly', False)]})
    # Current Document list revised filtered with Domain
    document_ids = fields.One2many('tech.submittal.document.revision', 'revision_id',
                                   string='Documents', readonly=True,
                                   states={'new': [('readonly', False)]}, domain=[('is_revised', '=', False)])
    # Revised Document list filtered with Domain
    revised_document_ids = fields.One2many('tech.submittal.document.revision', 'revision_id',
                                           string='Revised Documents', readonly=True, domain=[('is_revised', '=', True)])
    # Full Document List with out filter
    all_document_ids = fields.One2many('tech.submittal.document.revision', 'revision_id',
                                           string='All Documents', readonly=True)
    # Delivered Information
    delivery_ids = fields.One2many('tech.delivery.details', 'revision_id',
                                   "Deliveries", readonly=True, states={'submitted': [('readonly', False)]})
    delivered_qty = fields.Float(compute=total_delivery, string='Delivered Qty', store=False)
    balance_qty = fields.Float(compute=total_delivery, string='Balance Qty', store=False)
    state = fields.Selection([('new', 'Draft'), ('approved', 'Approved'), ('submitted', 'Submitted'),
                              ('resubmitted', 'Superseded'), ('cancel', 'Cancelled')], "Status",
                             readonly=False, default='new', track_visibility='onchange')
    dwg_count = fields.Integer(compute=total_delivery, string="No. Drawings", type='integer')
    # Drawing Creator Helper Wizard
    drawing_creator_ids = fields.Many2many('tech.drawing.creator', 'tech_revision_dwg_rel', 'revision_id', 'dwg_id',
                                           string="Drawing Creator"
                                           , readonly=True, states={'new': [('readonly', False)]})
    # Show Delivery Quantity Warning in case if more than the BBS
    qty_warning = fields.Char(type='char', string="Warning", readonly=True)
    # To calculate total Draft time
    total_draft_time = fields.Float(compute=total_delivery, string="Drafting Time", store=False)
    # Reason for Revision
    reason_id = fields.Many2one('tech.submittal.revision.reason', string="Reason",
                               readonly=True,states={'new': [('readonly', False)]}, help="Common Reason for revision")

    # Show reason on Submittal Sheet Print
    show_reason = fields.Boolean('Print Reason', help="Show Reason on Submittal Print ", default=False)
    # Is as build Submittal
    as_built = fields.Boolean('As-Built', help="Is This As-Built Submittal ?", dafault=False)

    _order = 'submittal_date desc'

    _sql_constraints = [('unique_ref_no', 'unique(ref_no)', ' Revision # Should be Unique')]

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        """
         Init form view  set Run Time Domain  for two fields signed_by  and Drawing Creator Ids
         Signed_by :  filed should filter allowed manager ID for logged in user
         Drawing Creator : Should show only the Created from the current record.
        """
        res = super(SubmittalRevision, self).fields_view_get(view_id=view_id, view_type=view_type,
                                                      toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            for field in res['fields']:
                if field == 'signed_by':
                    res1 = []
                    _user_obj = self.env.user.allowed_digital_sign_ids
                    for m in _user_obj:
                        res1.append(m.sign_manager_id.id)
                    res['fields'][field]['domain'] = [('id', 'in', res1)]
                if field == 'drawing_creator_ids':
                    result = []
                    for d in self.drawing_creator_ids:
                        result.append(d.id)
                    res['fields'][field]['domain'] = [('id', 'in', result)]
        return res

    @api.onchange('delivery_ids')
    def onchange_delivery(self):
        """Check On Delivery Ids Change if Delivery  Qty is Greater than BBS Qty in
         For the current submittal
        """
        _total_delivery = sum(r['delivered_qty'] for r in self.delivery_ids)
        if _total_delivery > self.bbs_weight:
            self.qty_warning = 'Delivery Qty is more than BBS Qty'
        else:
            self.qty_warning = ''

    @api.onchange('drawing_creator_ids')
    def onchange_drawing(self):
        """
         Onchange Helper wizards for Documents
         Create a list of documents as per the wizards parameters
         """
        line_dwg = []
        _rev_no = 'R0'  # Set Revision as R0 in case for blank Status
        if self.parent_id:  # If parent_id available change Number as per the revision
            _rev_no = 'R' + str(self.parent_id.revision_number + 1)
        if self.drawing_creator_ids:
            # get document type for drawing
            _dwg_type = self.env['tech.document_type'].search([('suffix', '=', 'DWG')])
            _dwg_type_id = _dwg_type and _dwg_type.id
            for dwg_obj in self.drawing_creator_ids:
                _prefix = ''
                _suffix = ''
                if dwg_obj.status:
                    _rev_no = dwg_obj.status
                if dwg_obj.name:
                    _prefix = dwg_obj.name + '-'
                if dwg_obj.suffix:
                    _suffix = '-' + dwg_obj.suffix
                for r in range(dwg_obj.start_no, dwg_obj.end_no + 1):
                    line_dwg.append({'name': _prefix + str(r).zfill(dwg_obj.padding_zero) +_suffix ,
                                     'document_type_id': _dwg_type_id,
                                     'description': dwg_obj.description,
                                     'document_status': _rev_no,
                                     'date': self.submittal_date,
                                     'created_by': self.submitted_by,
                                     })
            self.document_ids = line_dwg

    @api.multi
    def mark_submit(self):
        """Change Status on button Click"""
        return self.write({'state': 'submitted'})

    @api.multi
    def delete_revision(self):
        """ Delete option for cancelled Revision : button access set to state cancel and admin group to avoid user"""
        self.ensure_one()
        return super(SubmittalRevision, self).unlink()

    @api.multi
    def mark_draft(self):
        """Change Status on button Click"""
        return self.write({'state': 'new'})

    @api.multi
    def set_approved(self):
        """Change Status on button Click"""
        return self.write({'state': 'approved'})

    def _generate_new_ref(self, job_site_id):
        """
            Generates a Code for Submittal revision
            :returns: a dictionary with all information
            :parameter job_site_id : Selected Job Site to generate New Code
         """
        _sub_count_on_project = 1   # Set Count of submittal on project = 1
        _sub_count_on_global = 1   # Set Count of all submittal = 1
        submittal_obj = self.env['tech.submittal']
        _job_site = self.env['cicon.job.site'].browse(job_site_id)
        _company_id = self.env.user.company_id.id
        #   Get Last saved Submittal for Job SIte
        sub_id = submittal_obj.search([('job_site_id', '=', job_site_id)], order='id desc', limit=1)
        if sub_id:
            _sub_count_on_project = sub_id.submittal_project_count + 1
        #   Get Last saved Submittal for global count
        _sub_count_id = submittal_obj.search([], order='id desc', limit=1)
        if _sub_count_id:
            _sub_count_on_global = _sub_count_id.submittal_common_count + 1
        _prefix = 'CDS-'    # Set default Prefix for Submittal
        # Add up Prefix for Company if set or C
        _prefix += self.env['res.company'].browse(_company_id).submittal_prefix or 'C'
        # Create Submittal Code
        _sub_name = _prefix + '-' + str(_sub_count_on_global).zfill(3) + '-' + _job_site.site_ref_no + '-' + str(_sub_count_on_project).zfill(3)
        # Create Submittal Revision Code
        _ref_no = _sub_name + '-R0'
        return {'_sub_name': _sub_name,
                '_ref_no': _ref_no,
                '_sub_count_on_project': _sub_count_on_project,
                '_sub_count_common': _sub_count_on_global}

    @api.onchange('job_site_id')
    def onchange_project(self):
        """
            On Change Project To Set Site information on Current Submittal Revision form
            :raise warning if it job site not include site ref and co ordinates
        """
        if self.job_site_id:
            if self.job_site_id.site_ref_no and self.job_site_id.coordinator_id:
                rev_no = 0
                if self.submittal_id:   # if it is revision > 0 then Set Submittal name as it is
                    _sub_name = self.submittal_id.name
                    if self.parent_id:  # if parent_id  (revision > 0) then Set Submittal name as it is
                        rev_no = self.parent_id.revision_number + 1
                        _ref_no = self.parent_id.submittal_id.name + '-R' + str(rev_no)
                else:   # if new Submittal with revision 0
                    _new_submittal = self._generate_new_ref(self.job_site_id.id)
                    _ref_no = _new_submittal['_ref_no']     # New Code
                    _sub_name = _new_submittal['_sub_name']     # New submittal Name
                self.site_ref_no = self.job_site_id.site_ref_no # Fields in tech.submittal (master class)
                self.coordinator_id = self.job_site_id.coordinator_id.id    # Fields in tech.submittal (master class)
                self.revision_number = rev_no
                self.ref_no = _ref_no
                self.name = _sub_name   # Fields in tech.submittal (master class)
            else:
                    _warn = {
                        'title': 'Warning',
                        'message': 'Please Set Site Reference & Coordinator for Job Site'
                              }
                    return {'warning': _warn}

    @api.onchange('parent_id')
    def onchange_parent(self):
        """
        On Change ParentId
        trigger if creates revision
        """
        if self.parent_id:
            _docs = []
            _rev = self.parent_id.revision_number + 1
            # if documents also need revision
            for d in self.parent_id.document_ids:
                # find status and update if last char isdigit +1
                _status = d.document_status
                _rev_val = _status[-1]
                if _rev_val.isdigit():
                    _status = _status[:-1] + str((int(_status[-1]) + 1))
                else:
                    _status += str(_rev)
                _docs.append({'name': d.name,
                              'document_type_id': d.document_type_id.id,
                              'description': d.description,
                              'document_status': _status,
                              'rev_no': d.rev_no + 1,
                              'parent_id': d.id,
                              'draft_time': 0,
                              'document_id': d.document_id.id,
                              })
            #   Update Subject if it is revision > 0
            if _rev < 2:
                self.subject = self.parent_id.subject + '-revised'
            else:
                self.subject = self.parent_id.subject
            self.document_ids = _docs
            self.signed_by = self.parent_id.signed_by.id
            self.job_site_contact = self.parent_id.job_site_contact.id
            self.as_built = self.parent_id.as_built

    @api.onchange('submittal_id')
    def onchange_submittal(self):
        """
            On Change submittal_id
            trigger if creates revision Show information in Master Submittal
        """
        if self.submittal_id:
            self.name = self.submittal_id.name  # Fields in tech.submittal
            self.partner_id = self.submittal_id.partner_id.id   # Fields in tech.submittal
            self.job_site_id = self.submittal_id.job_site_id.id # Fields in tech.submittal

    @api.onchange('reason_id')
    def onchange_reason(self):
        if self.reason_id:
            for d in self.document_ids:
                if not d.reason_id:
                    d.reason_id = self.reason_id

    @api.multi
    def print_revision(self):
        """Print Submittal form button click and
         set status to submitted
        """
        self.ensure_one()
        self.write({'state': 'submitted'})
        return self.env['report'].get_action(self, 'cicon_tech.report_submittal_template')

    @api.multi
    def submittal_revision(self):
        """ Create revision
         :return : action to show form view with default submittal
         and parent id , on change of these fields will fill up  the rest
        """
        self.ensure_one()   # One Record
        # Find form view and pass context for default values
        form_id = self.env.ref('cicon_tech.tech_submittal_revision_form_view')
        ctx = dict(
            default_submittal_id=self.submittal_id.id,
            default_parent_id=self.id,
        )
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'tech.submittal.revision',
            'views': [(form_id.id, 'form')],
            'view_id': form_id.id,
            'target': 'current',
            'context': ctx,
        }

    @api.multi
    def send_email(self):
        """
         Show Email Template with exact print Format
         :return : Wizard form view for compose email
        """
        self.ensure_one()
        # Finds Email Template
        template = self.env.ref('cicon_tech.submittal_email_template')
        # Form view for Compose Email
        compose_form = self.env.ref('mail.email_compose_message_wizard_form')
        ctx = dict(
            default_model='tech.submittal.revision',
            default_res_id=self.id,
            default_use_template=bool(template),
            default_template_id=template.id,
            default_composition_mode='comment',
        )
        return {
            'name': 'Compose Email',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx,
        }

    @api.model
    def create(self, vals):
        """
        :param vals: create values for create
        :return : created new id

        """
        if vals.get('ref_no') is None:  # Check if ref_no , can be blank as form view using it as readonly mode
            if vals.get('name') and vals.get('submittal_id') == False:  # Check it is new Revision
                # Create new Code for selected Job Site
                _new_revision = self._generate_new_ref(vals.get('job_site_id'))
                _new_ref = _new_revision['_ref_no']
                vals.update({'name': _new_revision['_sub_name']})
                vals.update({'submittal_common_count': _new_revision['_sub_count_common']})
                vals.update({'submittal_project_count': _new_revision['_sub_count_on_project']})
            elif vals.get('submittal_id'):  # if is it a revision for Existing submittal
                _sub_name = self.env['tech.submittal'].browse(vals.get('submittal_id')).name
                _new_ref = _sub_name + "-R" + str(vals.get('revision_number'))
            vals.update({'ref_no': _new_ref})
        res = super(SubmittalRevision, self).create(vals)
        #   If there is parent_id then change the status to "resubmitted"
        if res:
            _rec = res.parent_id
            _rec.write({'state': 'resubmitted'})
        return res

    @api.multi
    def unlink(self):
        """ Override ORM delete
        Record not deleted , Just set  State to Cancel
           """
        for r in self:
            if r.state == 'resubmitted':
                raise UserError('Error', 'Cannot be Deleted ,Revision Superseded')
            # Check if parent Id and state resubmitted then change to active state 'submitted'
            if r.parent_id:
                if r.parent_id.state == 'resubmitted':
                    r.parent_id.write({'state': 'submitted'})
                    for doc in r.parent_id.revised_document_ids:
                                doc.write({'is_revised': False})
        return self.write({'state': 'cancel'})


SubmittalRevision()
