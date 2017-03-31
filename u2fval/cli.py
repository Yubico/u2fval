from __future__ import absolute_import

from wsgiref.simple_server import make_server
from werkzeug.exceptions import NotFound
from werkzeug.wsgi import pop_path_info
from . import app
from .model import db, Client
from six.moves.urllib_parse import urlparse
import os
import re
import sys
import click


NAME_PATTERN = re.compile(r'^[a-zA-Z0-9-_.]{3,}$')


def ensure_valid_name(name):
    if len(name) < 3:
        raise ValueError('Client names must be at least 3 characters')
    if len(name) > 40:
        raise ValueError('Client names must be no longer than 40 characters')
    if not NAME_PATTERN.match(name):
        raise ValueError('Client names may only contain the characters a-z, '
                         'A-Z, 0-9, "." (period), "_" (underscore), and "-" '
                         '(dash)')


CLICK_CONTEXT_SETTINGS = dict(
    help_option_names=['-h', '--help'],
    max_content_width=999
)


@click.group(context_settings=CLICK_CONTEXT_SETTINGS)
@click.option('--config', help='Specify configuration file.')
def cli(config):
    """
    u2fval command line tool

    Specify a configuration file to use by setting the U2FVAL_SETTINGS
    environment variable (or use the --config option).

    Use u2fval COMMMAND --help for help on a specific command.
    """
    if config:
        app.config.from_pyfile(os.path.abspath(config))


@cli.group('db')
def database():
    pass


@database.command()
def init():
    """Initializes the database by creating the tables."""
    db.create_all()
    click.echo('Database initialized!')


@cli.group()
def client():
    pass


@client.command('list')
def _list():
    """List the existing clients"""
    for c in Client.query.all():
        click.echo(c.name)


def _get_facets(ctx, appid, facets):
    if facets:
        return list(facets)
    url = urlparse(appid)
    if appid == '%s://%s' % (url.scheme, url.netloc):
        return [appid]
    ctx.fail("At least one facet is required unless appId is an origin")


@client.command()
@click.pass_context
@click.argument('name')
@click.argument('appId')
@click.argument('facets', nargs=-1)
def create(ctx, name, appid, facets):
    """
    Create a new client

    If no FACETS are given and the APPID is a valid web origin, the APPID will
    be used as the only valid facet.
    """
    ensure_valid_name(name)
    db.session.add(Client(name, appid, _get_facets(ctx, appid, facets)))
    db.session.commit()
    click.echo('Client created: %s' % name)


@client.command()
@click.argument('name')
def show(name):
    """Display information about a client"""
    c = Client.query.filter(Client.name == name).one()
    click.echo('Client: %s' % c.name)
    click.echo('AppID: %s' % c.app_id)
    click.echo('FacetIDs:')
    for facet in c.valid_facets:
        click.echo('  %s' % facet)
    click.echo('Users: %d' % c.users.count())


@client.command(help='set the appId and valid facets for an existing client')
@click.pass_context
@click.argument('name')
@click.argument('appId')
@click.argument('facets', nargs=-1)
def update(ctx, name, appid, facets):
    """Change the AppID and valid facets for a client"""
    c = Client.query.filter(Client.name == name).one()
    c.app_id = appid
    c.valid_facets = _get_facets(ctx, appid, facets)
    db.session.commit()
    click.echo('Client updated: %s' % name)


@client.command()
@click.argument('name')
def delete(name):
    """Deletes a client"""
    c = Client.query.filter(Client.name == name).one()
    db.session.delete(c)
    db.session.commit()
    click.echo('Client deleted: %s' % name)


def client_from_path(app):
    def inner(environ, start_response):
        client_name = pop_path_info(environ)
        if not client_name:
            return NotFound()(environ, start_response)

        environ['REMOTE_USER'] = client_name
        return app(environ, start_response)
    return inner


@cli.command()
@click.option('-i', '--interface', default='localhost',
              help='network interface to bind to')
@click.option('-p', '--port', default=8080, help='port to bind to')
@click.option('-c', '--client', help='run in single client mode')
@click.option('-d', '--debug', is_flag=True,
              help='run the debug server in multi-client mode, using '
              'http://CLIENT@... to specify client, with no authentication.')
def run(interface, port, client, debug):
    """Runs a U2FVAL server"""
    if debug:
        app.config['DEBUG'] = True
        click.echo("Starting debug server on http://%s:%d..." % (
            interface, port))
        return app.run(interface, port, debug)

    application = app
    extra_environ = {}
    if client:
        Client.query.filter(Client.name == client).one()
        click.echo("Running in single-client mode for client: '%s'" % client)
        extra_environ['REMOTE_USER'] = client
    else:
        click.echo("Running in multi-client mode with client specified in the "
                   "path")
        application = client_from_path(app)

    httpd = make_server(interface, port, application)
    httpd.base_environ.update(extra_environ)
    click.echo("Starting server on http://%s:%d..." % (interface, port))
    return httpd.serve_forever()


def main():
    try:
        cli(obj={})
    except ValueError as e:
        print('Error:', e)
        return 1


if __name__ == '__main__':
    sys.exit(main())
