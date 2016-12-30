#!/usr/bin/env python3

import os
import sys
import logging
import godaddypy
import configparser
import lesophos

parent_path = os.path.dirname(os.path.abspath(__file__))

config_parser = configparser.ConfigParser()
config_parser.read(os.path.join(parent_path, 'keys'))
try:
    api_key = config_parser['go_daddy']['api_key']
    api_secret = config_parser['go_daddy']['api_secret']
except:
    print("Problem reading API key/secret from keys file")
    sys.exit(1)


my_acct = godaddypy.Account(api_key=api_key, api_secret=api_secret)
client = godaddypy.Client(my_acct)

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)


def _get_zone(domain):
    parts = domain.split(".")
    zone_parts = parts[-2::]
    zone = ".".join(zone_parts)
    return zone


def _get_subdomain_for(domain, zone):
    subdomain = domain[0:(-len(zone)-1)]
    return subdomain


def _update_dns(domain, token):
    challengedomain = "_acme-challenge." + domain
    logger.info(" + Updating TXT record for {0} to '{1}'.".format(challengedomain, token))
    zone = _get_zone(challengedomain)
    # logger.info("Zone to update: {0}".format(zone))
    subdomain = _get_subdomain_for(challengedomain, zone)
    # logger.info("Subdomain name: {0}".format(subdomain))

    record = {
        'name': subdomain,
        'data': token,
        'ttl': 600,
        'type': 'TXT'
    }
    result = client.update_record(zone, record)
    if result is not True:
        logger.warn("Error updating record for domain {0}.".format(domain))


def create_txt_record(args):
    domain, token = args[0], args[2]
    _update_dns(domain, token)


def delete_txt_record(args):
    domain = args[0]
    # using client.delete_record() is dangerous. null it instead!
    # https://github.com/eXamadeus/godaddypy/issues/13
    _update_dns(domain, "null")


def deploy_cert(args):
    domain, privkey_pem, cert_pem, fullchain_pem, chain_pem, timestamp = args
    logger.info(' + ssl_certificate: {0}'.format(fullchain_pem))
    logger.info(' + ssl_certificate_key: {0}'.format(privkey_pem))
    logger.info('deploying certificate for {0}'.format(domain))
    instance = lesophos.Cron(os.path.dirname(os.path.abspath(__file__)))
    instance.deploy_hook(domain)


    print (fullchain_pem)
    print (privkey_pem)
    return


def unchanged_cert(args):
    return


def main(argv):
    ops = {
        'deploy_challenge': create_txt_record,
        'clean_challenge' : delete_txt_record,
        'deploy_cert'     : deploy_cert,
        'unchanged_cert'  : unchanged_cert,
    }
    logger.info(" + Godaddy hook executing: {0}".format(argv[0]))
    ops[argv[0]](argv[1:])


if __name__ == '__main__':
    main(sys.argv[1:])
