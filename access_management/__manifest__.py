{
    'name': 'Access Management',
    'summary': 'Conservative, profile-based access restrictions',
    'version': '19.0.1.0.0',
    'category': 'Administration/Technical',
    'license': 'LGPL-3',
    'author': 'Custom',
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/access_management_security.xml',
        'security/ir.model.access.csv',
        'views/access_management_views.xml',
    ],
    'application': True,
    'installable': True,
}
