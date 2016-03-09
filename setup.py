# Copyright (c) 2014 Yubico AB
# All rights reserved.
#
#   Redistribution and use in source and binary forms, with or
#   without modification, are permitted provided that the following
#   conditions are met:
#
#    1. Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#    2. Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

from __future__ import print_function
from u2fval.yubicommon.setup import setup
import sys
import os
import glob


# Make sure the cont/u2fval.conf file exists and is a copy of
# u2fval/default_settings.py
if [_ for _ in ['install', 'sdist'] if _ in sys.argv[1:]]:
    print("copying default settings...")
    source = os.path.abspath('u2fval/default_settings.py')
    target = os.path.abspath('conf/u2fval.conf')
    with open(target, 'w') as target_f:
        with open(source, 'r') as source_f:
            target_f.write(source_f.read())
    os.chmod(target, 0o600)


def can_write_etc(path=os.path.join(os.path.sep, 'etc', 'yubico', 'u2fval')):
    if not os.path.isdir(path):
        return can_write_etc(os.path.dirname(path))
    return os.access(path, os.W_OK)


# Only write configuration files if we have the correct permissions.
data_files = [
    ('/etc/yubico/u2fval', ['conf/u2fval.conf', 'conf/logging.conf']),
    ('/etc/yubico/u2fval/metadata', glob.glob('conf/metadata/*.json'))
] if can_write_etc() else []

setup(
    name='u2fval',
    author='Dain Nilsson',
    author_email='dain@yubico.com',
    maintainer='Yubico Open Source Maintainers',
    maintainer_email='ossmaint@yubico.com',
    description='Standalone/WSGI U2F server implementing the U2FVAL protocol',
    url='https://github.com/Yubico/u2fval',
    license='BSD 2 clause',
    entry_points={
        'console_scripts': ['u2fval=u2fval.cli:main']
    },
    data_files=data_files,
    install_requires=['python-u2flib-server>=4.0', 'SQLAlchemy',
                      'WebOb', 'cachetools'],
    test_suite='test',
    tests_require=['WebTest'],
    extras_require={
        'u2fval:python_version=="2.6"': ['argparse'],
        'memcache': ['python-memcached'],
        'db_migration': ['alembic']
    },
    classifiers=[
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Internet',
        'Topic :: Security',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application'
    ]
)
