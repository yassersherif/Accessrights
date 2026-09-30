{
    'name': 'Access Management',
    'summary': 'Advanced access management for Odoo',
    'version': '19.0.1.0.0',
    'category': 'Administration/Technical',
    'license': 'LGPL-3',
    'author': 'Yasser Sherif',
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/access_management_security.xml',
        'security/ir.model.access.csv',
        'views/access_management_views.xml',
    ],
    'application': True,
    'installable': True,
}
