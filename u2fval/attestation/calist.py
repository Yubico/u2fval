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

import os
import logging
from M2Crypto import X509

__all__ = ['CAListVerifier']
log = logging.getLogger(__name__)


class CAListVerifier(object):

    def __init__(self):
        self._ca_certs = {}

    def __call__(self, cert):
        issuer = cert.get_issuer().as_der()
        for ca in self._ca_certs.get(issuer, []):
            if cert.verify(ca.get_pubkey()) == 1:
                return
        raise ValueError('Certificate not issued by a trusted CA!')

    def add_ca(self, ca):
        subject = ca.get_subject().as_der()
        existing = self._ca_certs.get(subject, [])
        existing.append(ca)
        self._ca_certs[subject] = existing

    def load_ca_from_pem(self, pem):
        self.add_ca(X509.load_cert_string(pem))

    def add_ca_dir(self, dirname):
        for fname in os.listdir(dirname):
            try:
                with open(fname, 'r') as f:
                    self.add_ca_from_pem(f.read())
            except:
                log.exception('Unable to load CA cert from file: %s', fname)
