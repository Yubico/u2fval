#    Copyright (C) 2014  Yubico AB
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.


import os
import sys
import argparse


def run_parser(parser):
    parser.add_argument('-i', '--interface', default='localhost',
                        help='network interface to bind to')
    parser.add_argument('-p', '--port', type=int, default=8080,
                        help='TCP port to bind to')
    parser.add_argument('-c', '--client', help='run in single client mode '
                        'using CLIENT')


def client_parser(parser):
    class NameFromFacetsAction(argparse.Action):
        def __call__(self, parser, args, values, option_string=None):
            if not values:
                if args.facets and len(args.facets) > 1:
                    values, args.facets = args.facets[-1], args.facets[:-1]
                else:
                    parser.error('argument %s is required' % self.dest)
            args.name = values

    client_subparsers = parser.add_subparsers(dest='action', help='subcommand')

    list_parser = client_subparsers.add_parser('list',
                                               help='list available clients')

    create_parser = client_subparsers.add_parser('create',
                                                 help='create a client')
    create_parser.add_argument('name', metavar='<name>', nargs='?',
                               action=NameFromFacetsAction,
                               help='the name of the client')
    create_parser.add_argument('-a', '--appId', required=True,
                               help='sets the appId')
    create_parser.add_argument('-f', '--facets', required=True, nargs='+',
                               metavar='FACET',
                               help='all valid facets for the client')

    show_parser = client_subparsers.add_parser('show',
                                               help='display a client')
    show_parser.add_argument('name', metavar='<name>',
                             help='the name of the client')

    update_parser = client_subparsers.add_parser('update',
                                                 help='update data for a '
                                                 'client')
    update_parser.add_argument('name', metavar='<name>', nargs='?',
                               action=NameFromFacetsAction,
                               help='the name of the client')
    update_parser.add_argument('-a', '--appId',
                               help='sets the appId')
    update_parser.add_argument('-f', '--facets', nargs='+', metavar='FACET',
                               help='all valid facets for the client')

    delete_parser = client_subparsers.add_parser('delete',
                                                 help='delete a client')
    delete_parser.add_argument('name', metavar='<name>',
                               help='the name of the client')


def db_parser(parser):
    parser.add_argument('action', choices=['init'], help='subcommand')


def arg_parser():
    parser = argparse.ArgumentParser(
        description="Yubico U2F Validation Server",
        add_help=True
    )
    parser.add_argument('-c', '--config', help='specify an alternate '
                        'configuration file to use')
    parser.add_argument('-d', '--debug', action='store_true', dest='debug',
                        help='prints debug information to stdout')
    subparsers = parser.add_subparsers(dest='command',
                                       help='available commands')

    run_parser(subparsers.add_parser('run', help='run the server'))
    client_parser(subparsers.add_parser('client', help='manage clients'))
    db_parser(subparsers.add_parser('db', help='manage database'))

    return parser


def create_session(settings, echo=False):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(settings['db'], echo=echo)

    Session = sessionmaker(bind=engine)
    return Session()


def handle_client(settings, args):
    from u2fval.client.controller import ClientController
    session = create_session(settings, args.debug)
    controller = ClientController(session)

    cmd = args.action
    if cmd == 'list':
        for client in controller.list_clients():
            print client
    else:
        try:
            if cmd == 'create':
                controller.create_client(args.name, args.appId, args.facets)
                print 'Created client: %s' % args.name
            elif cmd == 'show':
                client = controller.get_client(args.name)
                print 'Client: %s' % client.name
                print 'AppID: %s' % client.app_id
                print 'FacetIDs:'
                for facet in client.valid_facets:
                    print '  %s' % facet
            elif cmd == 'update':
                controller.update_client(args.name, args.appId, args.facets)
                print 'Updated client: %s' % args.name
            elif cmd == 'delete':
                controller.delete_client(args.name)
                print 'Deleted client: %s' % args.name
            session.commit()
        except Exception as e:
            print e
            if args.debug:
                raise e
            sys.exit(1)


def handle_run(settings, args):
    from u2fval.core.api import create_application
    from u2fval.client.pathinfo_auth import client_from_pathinfo
    from u2fval.client.controller import ClientController
    from wsgiref.simple_server import make_server

    extra_environ = {}
    if args.client:
        # Ensure the existance of the client.
        session = create_session(settings, args.debug)
        controller = ClientController(session)
        controller.get_client(args.client)
        session.close()
        print "Running in single-client mode for client: '%s'" % args.client
        extra_environ['REMOTE_USER'] = args.client
        application = create_application(settings)
    else:
        application = client_from_pathinfo(create_application(settings))
    httpd = make_server(args.interface, args.port, application)
    httpd.base_environ.update(extra_environ)
    print "Starting server on http://%s:%d..." % (args.interface, args.port)
    httpd.serve_forever()


def handle_db(settings, args):
    from u2fval.model import Base
    from sqlalchemy import create_engine

    engine = create_engine(settings['db'], echo=args.debug)
    Base.metadata.create_all(engine)
    print "Database intialized!"


def handle_args(settings, args):
    cmd = args.command
    if cmd == 'client':
        handle_client(settings, args)
    elif cmd == 'run':
        handle_run(settings, args)
    elif cmd == 'db':
        handle_db(settings, args)


def main():
    args = arg_parser().parse_args()

    if args.config:
        os.environ['U2FVAL_SETTINGS'] = args.config
    from u2fval.config import settings

    handle_args(settings, args)


if __name__ == '__main__':
    main()
