#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright 2016-2017 René Klomp
#
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

import subprocess
import sys
import time

cc = '/usr/local/bin/confd-client.plx'


def openssl_get(domain, param):
    cmd_param=param
    if param == "altnames":
        cmd_param="text"
    cmd = "openssl x509 -noout -in /root/.getssl/%s/%s.crt -%s" % (domain,domain,cmd_param)
    value = subprocess.check_output(cmd, shell=True).strip()
    if param in ['startdate','enddate','fingerprint','serial']:
        return value.split('=')[1]
    if param in ['issuer','subject']:
        return value.split('/')[-1]
    if param == "altnames":
        i = iter(value.splitlines())
        for line in i:
            if 'X509v3 Subject Alternative Name' in line:
                return "['%s']"% i.next().strip().replace(", ","','")
    return value


def update_cert(domain, cert_ref):
    print "Writing certificate for %s to object %s" % (domain, cert_ref)

    cert=subprocess.check_output("/usr/bin/openssl x509 -in /root/.getssl/%s/%s.crt -text" % (domain,domain), shell=True).replace('\n','\\n')
    key=open("/root/.getssl/%s/%s.key" % (domain,domain)).read().replace('\n','\\n')

    # There might be a better solution for this, but I cannot find any documentation on cc.
    cmd = """OBJS
    ca
    host_key_cert
    %s
    certificate="%s"
    key="%s"
    write""" % (cert_ref, cert, key)

    cert_object = subprocess.Popen([cc, '-batch'],  stdin=subprocess.PIPE, stdout=subprocess.PIPE).communicate(input=cmd)[0]

    for line in cert_object.split("\n"):
        if "'meta' =>" in line:
             return line.split('>')[1][2:-2]


def update_meta(domain, meta_ref):
    print "Updating certificate meta to object %s" % meta_ref

    cmd = """OBJS
    ca
    meta_x509
    %s
    vpn_id="%s"
    startdate="%s"
    enddate="%s"
    fingerprint="%s"
    serial="%s"
    issuer="%s"
    issuer_hash="%s"
    name="%s"
    subject="%s"
    subject_hash="%s"
    subject_alt_names=%s
    write""" % (
        meta_ref,domain,
        openssl_get(domain,'startdate'),
        openssl_get(domain,'enddate'),
        openssl_get(domain,'fingerprint'),
        openssl_get(domain,'serial'),
        openssl_get(domain,'issuer'),
        openssl_get(domain,'issuer_hash'),
        openssl_get(domain,'subject'),
        openssl_get(domain,'subject'),
        openssl_get(domain,'subject_hash'),
        openssl_get(domain,'altnames')
    )

    subprocess.Popen([cc, '-batch'],  stdin=subprocess.PIPE, stdout=subprocess.PIPE).communicate(input=cmd)[0]


def main():
    if not len(sys.argv) == 3:
        print "Usage %s <domain> <cert_ref>" % sys.argv[0]
        sys.exit(1)

    domain = sys.argv[1]
    cert_ref = sys.argv[2]

    meta_ref = update_cert(domain,cert_ref)
    update_meta(domain,meta_ref)

    print "Done!"
    # Wait for a few seconds for the config to be applied so ssl check after this script will succeed
    time.sleep(5)

if __name__ == "__main__":
    main()
