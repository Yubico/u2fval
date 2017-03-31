from __future__ import print_function

# flake8: noqa
import os
os.environ['U2FVAL_SETTINGS'] = '/dev/null'  # Avoid loading config file
from u2fval import app
from u2fval.model import db, Certificate, _calculate_fingerprint
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import click


@click.command()
@click.argument('db-uri')
def rewrite_certs(db_uri):
    """Re-caclulates fingerprints for all certificates"""
    click.confirm('Re-calculate certificate fingerprints?', abort=True)

    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri

    changed = 0
    total = 0
    for cert in Certificate.query.all():
        total += 1
        c = x509.load_der_x509_certificate(cert.der, default_backend())
        old_fp = cert.fingerprint
        new_fp = _calculate_fingerprint(c)
        if new_fp != old_fp:
            changed += 1
            cert.fingerprint = new_fp
    db.session.commit()
    click.echo('Success! %d/%d certificates were modified.' % (changed, total))


if __name__ == '__main__':
    rewrite_certs()
