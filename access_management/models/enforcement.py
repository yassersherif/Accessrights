"""Narrow, conservative server-side enforcement overlay.

This uses standard ``base`` inheritance.  It never returns True for an access
that Odoo itself rejected: native checks run first and this only raises an
additional AccessError.  Configuration and recovery administrators are
explicitly excluded to preserve the recovery path.
"""
import logging
from ast import literal_eval
from odoo import api, models, _
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)
_CONFIG_MODELS = frozenset({
    'access.management', 'access.management.menu.rule', 'access.management.model.rule',
    'access.management.field.rule', 'access.management.domain.rule', 'access.management.button.rule',
    'access.management.search.panel.rule', 'access.management.chatter.rule',
})

class AccessManagementEnforcement(models.AbstractModel):
    _inherit = 'base'

    def _am_is_exempt(self):
        if self._name in _CONFIG_MODELS or self.env.is_superuser():
            return True
        return self.env.user.has_group('access_management.access_management_group_recovery')

    def _am_profiles(self):
        if self._am_is_exempt():
            return self.env['access.management']
        # sudo is intentionally limited to reading access configuration; business
        # data are never read with sudo by this module.
        return self.env['access.management'].sudo().search([
            ('active', '=', True), ('user_ids', 'in', self.env.uid),
        ])

    def _am_model_rules(self, profiles):
        return profiles.model_rule_ids.filtered(lambda r: r.apply_filter and r.model_id.model == self._name)

    def _am_denied_operation(self, operation):
        profiles = self._am_profiles()
        if not profiles:
            return False
        for rule in self._am_model_rules(profiles):
            if not getattr(rule, 'perm_%s' % operation):
                return True
        # Global/read-only restrictions are deliberately scoped: no model scope,
        # no enforcement.  This prevents accidental installation-wide lockout.
        for profile in profiles:
            scoped = self.env['ir.model']._get(self._name) in profile.global_model_ids
            if scoped and ((operation == 'create' and (profile.read_only or profile.global_disable_create)) or
                           (operation == 'write' and (profile.read_only or profile.global_disable_write)) or
                           (operation == 'unlink' and (profile.read_only or profile.global_disable_delete))):
                return True
        return False

    def _am_raise_if_denied(self, operation):
        if self._am_denied_operation(operation):
            _logger.info('Access Management denied %s on model %s for uid %s', operation, self._name, self.env.uid)
            raise AccessError(_('Access Management profile denies %(operation)s on %(model)s.', operation=operation, model=self._name))

    def check_access_rights(self, operation, raise_exception=True):
        result = super().check_access_rights(operation, raise_exception=raise_exception)
        if result and not self._am_is_exempt() and self._am_denied_operation(operation):
            if raise_exception:
                self._am_raise_if_denied(operation)
            return False
        return result

    def _am_domains(self, operation):
        domains = []
        for rule in self._am_profiles().domain_rule_ids.filtered(lambda r: r.apply_filter and r.model_id.model == self._name and getattr(r, 'perm_%s' % operation)):
            try:
                domains.append(literal_eval(rule.domain))
            except (ValueError, SyntaxError, TypeError):
                _logger.warning('Ignoring invalid saved Access Management domain rule %s', rule.id)
        return domains

    def check_access_rule(self, operation):
        result = super().check_access_rule(operation)
        domains = self._am_domains(operation)
        if domains and self:
            # Every active rule is an additional AND constraint.  ``filtered_domain``
            # evaluates through the ORM, then compare IDs without exposing values.
            allowed = self
            for domain in domains:
                allowed = allowed.filtered_domain(domain)
            if len(allowed) != len(self):
                _logger.info('Access Management denied %s outside configured domain on %s for uid %s', operation, self._name, self.env.uid)
                raise AccessError(_('Access Management profile denies this record outside its configured domain.'))
        return result

    def _am_field_rules(self):
        return self._am_profiles().field_rule_ids.filtered(lambda r: r.model_id.model == self._name)

    def _am_denied_fields(self, names, write=False):
        denied = set()
        for rule in self._am_field_rules():
            if rule.field_id.name in names and ((write and (not rule.perm_write or rule.readonly)) or (not write and (not rule.perm_read or rule.invisible))):
                denied.add(rule.field_id.name)
        return denied

    def read(self, fields=None, load='_classic_read'):
        # ``fields=None`` asks the ORM for every field, so it must be treated as
        # a request for the restricted fields too (rather than as an empty set).
        requested = set(fields) if fields is not None else {
            rule.field_id.name for rule in self._am_field_rules()
        }
        denied = self._am_denied_fields(requested)
        if denied:
            raise AccessError(_('Access Management profile denies reading field(s): %s') % ', '.join(sorted(denied)))
        return super().read(fields=fields, load=load)

    def write(self, vals):
        denied = self._am_denied_fields(vals, write=True)
        if denied:
            raise AccessError(_('Access Management profile denies writing field(s): %s') % ', '.join(sorted(denied)))
        self._am_raise_if_denied('write')
        self.check_access_rule('write')
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        self._am_raise_if_denied('create')
        for vals in vals_list:
            denied = self._am_denied_fields(vals, write=True)
            if denied:
                raise AccessError(_('Access Management profile denies writing field(s): %s') % ', '.join(sorted(denied)))
        return super().create(vals_list)

    def unlink(self):
        self._am_raise_if_denied('unlink')
        self.check_access_rule('unlink')
        return super().unlink()

    def fields_get(self, allfields=None, attributes=None):
        result = super().fields_get(allfields=allfields, attributes=attributes)
        for rule in self._am_field_rules():
            if rule.field_id.name in result:
                if rule.invisible or not rule.perm_read:
                    result.pop(rule.field_id.name, None)
                elif rule.readonly or not rule.perm_write:
                    result[rule.field_id.name]['readonly'] = True
        return result
