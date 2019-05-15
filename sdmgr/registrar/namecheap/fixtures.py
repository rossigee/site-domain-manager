NAMECHEAP_CONTACT = {
    'organisation': "Authentic Produce Limited",
    'address1': "Floor 1, Liberation Station",
    'address2': "Esplanade",
    'city': "St Helier",
    'province': "Jersey",
    'postalcode': "JE2 3AS",
    'country': "JE",
    'phone': "+441903680080"
}

NAMECHEAP_DOMAIN_CONTACTS = {
    'registrant': NAMECHEAP_CONTACT + {
        'firstname': "Marcus",
        'lastname': "Quinn",
        'email': 'webmaster@authenticproduce.com'
    },
    'tech': NAMECHEAP_CONTACT + {
        'firstname': "Ross",
        'lastname': "Golder",
        'email': 'webmaster@authenticproduce.com'
    },
    'admin': NAMECHEAP_CONTACT + {
        'firstname': "Angelika",
        'lastname': "Kopacz",
        'email': 'webmaster@authenticproduce.com'
    }
}

NAMECHEAP_BILLING_CONTACT = NAMECHEAP_CONTACT + {
    'firstname': "Marcus",
    'lastname': "Quinn",
    'email': 'webmaster@authenticproduce.com'
}
