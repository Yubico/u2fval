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
from release import setup
import sys
import os


# Make sure the cont/u2fval.conf file exists and is a copy of
# u2fval/default_settings.py when building a release.
if [_ for _ in ['sdist'] if _ in sys.argv[1:]]:
    print("copying default settings...")
    source = os.path.abspath('u2fval/default_settings.py')
    target = os.path.abspath('conf/u2fval.conf')
    target_dir = os.path.dirname(target)
    if not os.path.isdir(target_dir):
        os.mkdir(target_dir)
    with open(target, 'w') as target_f:
        with open(source, 'r') as source_f:
            target_f.write(source_f.read())
    os.chmod(target, 0o600)


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
        'console_scripts': [
            'u2fval=u2fval.cli:main'
        ]
    },
    install_requires=[
        'python-u2flib-server >= 5, <6',
        'flask',
        'flask-sqlalchemy'
    ],
    test_suite='test',
    extras_require={
        'memcache': ['python-memcached']
    },
    classifiers=[
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Internet',
        'Topic :: Security',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application'
    ]
)
