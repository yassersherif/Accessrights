from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestAccessManagement(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].create({
            'name': 'Access profile test user', 'login': 'access_profile_test_user',
            'email': 'access-profile-test@example.invalid',
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.partner_model = cls.env['ir.model']._get('res.partner')

    def test_profiles_allow_multiple_users_and_archive(self):
        profile = self.env['access.management'].create({'name': 'Profile', 'user_ids': [(4, self.user.id)]})
        self.assertIn(self.user, profile.user_ids)
        profile.toggle_active()
        self.assertFalse(profile.active)

    def test_domain_requires_literal_list(self):
        with self.assertRaises(ValidationError):
            self.env['access.management.domain.rule'].create({
                'access_management_id': self.env['access.management'].create({'name': 'Profile'}).id,
                'model_id': self.partner_model.id, 'domain': "__import__('os').system('false')",
            })

    def test_restrictive_overlap_is_retained(self):
        first = self.env['access.management'].create({'name': 'first', 'user_ids': [(4, self.user.id)]})
        second = self.env['access.management'].create({'name': 'second', 'user_ids': [(4, self.user.id)]})
        self.env['access.management.model.rule'].create({
            'access_management_id': first.id, 'model_id': self.partner_model.id, 'perm_write': False,
        })
        self.assertTrue(second.overlap_warning)
