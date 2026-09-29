"""Configuration models for Access Management.

Profiles are *restrictive overlays*: native Odoo ACLs and record rules are
always evaluated first; this module can only deny further access.
"""

from ast import literal_eval

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


OPERATIONS = ('read', 'create', 'write', 'unlink')


class AccessManagement(models.Model):
    _name = 'access.management'
    _description = 'Access Management Profile'
    _order = 'name, id'

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    user_ids = fields.Many2many(
        'res.users',
        'access_management_user_rel',
        'profile_id',
        'user_id',
        string='Users',
    )
    read_only = fields.Boolean(
        help='Deny create, write and delete only for models explicitly scoped below.'
    )
    disable_developer_mode = fields.Boolean()
    apply_without_company = fields.Boolean(
        string='Apply Without Company',
        default=False,
    )
    global_model_ids = fields.Many2many(
        'ir.model',
        string='Global Model Scope',
        help='Empty means no global restriction is enforced.',
    )
    global_disable_create = fields.Boolean()
    global_disable_write = fields.Boolean()
    global_disable_delete = fields.Boolean()
    restrict_import = fields.Boolean()
    restrict_export = fields.Boolean()
    restrict_technical_menus = fields.Boolean()

    menu_rule_ids = fields.One2many(
        'access.management.menu.rule',
        'access_management_id',
    )
    model_rule_ids = fields.One2many(
        'access.management.model.rule',
        'access_management_id',
    )
    field_rule_ids = fields.One2many(
        'access.management.field.rule',
        'access_management_id',
    )
    domain_rule_ids = fields.One2many(
        'access.management.domain.rule',
        'access_management_id',
    )
    button_rule_ids = fields.One2many(
        'access.management.button.rule',
        'access_management_id',
    )
    search_panel_rule_ids = fields.One2many(
        'access.management.search.panel.rule',
        'access_management_id',
    )
    chatter_rule_ids = fields.One2many(
        'access.management.chatter.rule',
        'access_management_id',
    )

    rule_count = fields.Integer(compute='_compute_rule_count')
    overlap_warning = fields.Char(compute='_compute_overlap_warning')

    @api.depends(
        'menu_rule_ids',
        'model_rule_ids',
        'field_rule_ids',
        'domain_rule_ids',
        'button_rule_ids',
        'search_panel_rule_ids',
        'chatter_rule_ids',
    )
    def _compute_rule_count(self):
        for record in self:
            record.rule_count = sum(
                len(record[field_name])
                for field_name in (
                    'menu_rule_ids',
                    'model_rule_ids',
                    'field_rule_ids',
                    'domain_rule_ids',
                    'button_rule_ids',
                    'search_panel_rule_ids',
                    'chatter_rule_ids',
                )
            )

    @api.depends('user_ids', 'active')
    def _compute_overlap_warning(self):
        Profile = self.env['access.management'].sudo()

        for record in self:
            overlap = (
                Profile.search_count([
                    ('id', '!=', record.id),
                    ('active', '=', True),
                    ('user_ids', 'in', record.user_ids.ids),
                ])
                if record.user_ids
                else 0
            )

            record.overlap_warning = (
                _(
                    '%s active profile(s) overlap; every configured denial '
                    'is combined restrictively.'
                ) % overlap
                if overlap
                else False
            )

    @api.constrains(
        'user_ids',
        'global_model_ids',
        'read_only',
        'global_disable_create',
        'global_disable_write',
        'global_disable_delete',
    )
    def _check_recovery_scope(self):
        recovery = self.env.ref(
            'access_management.access_management_group_recovery',
            raise_if_not_found=False,
        )

        if not recovery:
            return

        for record in self:
            if (
                record.user_ids & recovery.user_ids
                and (
                    record.read_only
                    or record.global_disable_create
                    or record.global_disable_write
                    or record.global_disable_delete
                )
            ):
                raise ValidationError(_(
                    'Recovery administrators cannot be assigned an active '
                    'global or read-only restriction.'
                ))

    def action_view_rules(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'access.management',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _clear_access_management_caches(self):
        # Odoo caches method dispatch and menus; invalidating the registry
        # cache makes configuration changes effective on the next request.
        self.env.registry.clear_cache()

    def create(self, vals_list):
        records = super().create(vals_list)
        records._clear_access_management_caches()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._clear_access_management_caches()
        return result

    def unlink(self):
        result = super().unlink()
        self._clear_access_management_caches()
        return result


class AccessManagementRule(models.AbstractModel):
    _name = 'access.management.rule'
    _description = 'Access Management Rule Base'
    _abstract = True

    access_management_id = fields.Many2one(
        'access.management',
        required=True,
        ondelete='cascade',
        index=True,
    )
    note = fields.Char()

    def _invalidate(self):
        self.env['access.management']._clear_access_management_caches()

    def create(self, vals_list):
        records = super().create(vals_list)
        records._invalidate()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._invalidate()
        return result

    def unlink(self):
        result = super().unlink()
        self._invalidate()
        return result


class MenuRule(models.Model):
    _name = 'access.management.menu.rule'
    _inherit = 'access.management.rule'
    _description = 'Hidden Menu Rule'

    menu_id = fields.Many2one(
        'ir.ui.menu',
        required=True,
        ondelete='cascade',
    )
    hide_menu = fields.Boolean(default=True)


class ModelRule(models.Model):
    _name = 'access.management.model.rule'
    _inherit = 'access.management.rule'
    _description = 'Model Access Rule'

    model_id = fields.Many2one(
        'ir.model',
        required=True,
        ondelete='cascade',
    )
    perm_read = fields.Boolean(string='Allow Read', default=True)
    perm_create = fields.Boolean(string='Allow Create', default=True)
    perm_write = fields.Boolean(string='Allow Write', default=True)
    perm_unlink = fields.Boolean(string='Allow Delete', default=True)
    apply_filter = fields.Boolean(string='Enforce', default=True)


class FieldRule(models.Model):
    _name = 'access.management.field.rule'
    _inherit = 'access.management.rule'
    _description = 'Field Access Rule'

    model_id = fields.Many2one(
        'ir.model',
        required=True,
        ondelete='cascade',
    )
    field_id = fields.Many2one(
        'ir.model.fields',
        required=True,
        ondelete='cascade',
        domain="[('model_id', '=', model_id)]",
    )
    perm_read = fields.Boolean(string='Allow Read', default=True)
    perm_write = fields.Boolean(string='Allow Write', default=True)
    invisible = fields.Boolean()
    readonly = fields.Boolean()

    @api.constrains('model_id', 'field_id')
    def _check_field_model(self):
        for record in self:
            if (
                record.field_id
                and record.field_id.model_id != record.model_id
            ):
                raise ValidationError(_(
                    'The field must belong to the selected model.'
                ))


class DomainRule(models.Model):
    _name = 'access.management.domain.rule'
    _inherit = 'access.management.rule'
    _description = 'Domain Access Rule'

    model_id = fields.Many2one(
        'ir.model',
        required=True,
        ondelete='cascade',
    )
    domain = fields.Char(required=True, default='[]')
    perm_read = fields.Boolean(default=True)
    perm_create = fields.Boolean(default=True)
    perm_write = fields.Boolean(default=True)
    perm_unlink = fields.Boolean(default=True)
    apply_filter = fields.Boolean(default=True)

    @api.constrains('domain')
    def _check_domain(self):
        for record in self:
            try:
                value = literal_eval(record.domain)
                if not isinstance(value, list):
                    raise ValueError()
            except (ValueError, SyntaxError, TypeError):
                raise ValidationError(_(
                    'Domain must be a literal list; Python expressions '
                    'are not accepted.'
                ))


class ButtonRule(models.Model):
    _name = 'access.management.button.rule'
    _inherit = 'access.management.rule'
    _description = 'Button and Tab Rule'

    model_id = fields.Many2one(
        'ir.model',
        required=True,
        ondelete='cascade',
    )
    model_name = fields.Char(
        related='model_id.model',
        readonly=True,
    )
    view_id = fields.Many2one(
        'ir.ui.view',
        ondelete='cascade',
        domain="[('model', '=', model_name)]",
    )
    button_name = fields.Char()
    button_label = fields.Char()
    restriction_type = fields.Selection(
        [
            ('button', 'Button'),
            ('page', 'Notebook Page'),
        ],
        default='button',
        required=True,
    )
    hide_button = fields.Boolean(default=True)
    disable_button = fields.Boolean()
    page_name = fields.Char()
    hide_kanban_link = fields.Boolean(
        string='Hide Kanban Link',
        default=False,
    )


class SearchPanelRule(models.Model):
    _name = 'access.management.search.panel.rule'
    _inherit = 'access.management.rule'
    _description = 'Search Panel Rule'

    model_id = fields.Many2one(
        'ir.model',
        required=True,
        ondelete='cascade',
    )
    view_id = fields.Many2one(
        'ir.ui.view',
        ondelete='cascade',
    )
    field_id = fields.Many2one(
        'ir.model.fields',
        required=True,
        ondelete='cascade',
        domain="[('model_id', '=', model_id)]",
    )
    invisible = fields.Boolean(default=True)


class ChatterRule(models.Model):
    _name = 'access.management.chatter.rule'
    _inherit = 'access.management.rule'
    _description = 'Chatter Rule'

    model_id = fields.Many2one(
        'ir.model',
        required=True,
        ondelete='cascade',
    )
    view_chatter = fields.Boolean(default=True)
    read_messages = fields.Boolean(default=True)
    post_messages = fields.Boolean(default=True)
    edit_messages = fields.Boolean(default=True)
    delete_messages = fields.Boolean(default=True)
    add_attachments = fields.Boolean(default=True)
    download_attachments = fields.Boolean(default=True)
    manage_followers = fields.Boolean(default=True)
    view_activities = fields.Boolean(default=True)
    create_activities = fields.Boolean(default=True)
    edit_activities = fields.Boolean(default=True)
    delete_activities = fields.Boolean(default=True)