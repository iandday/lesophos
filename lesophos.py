import os
import subprocess
from io import StringIO
# from time import gmtime, strftime, sleep
from time import sleep
from scp import SCPClient
import json
import paramiko
import re
import argparse
import logging




class SetupEnvironment():
    def __init__(self, base, host, key, logger=None):
        self._base_dir = base
        self._host = host
        self._key = key
        self._domains = {}
        self.logger = logger or logging.getLogger(__name__)

    def setup(self):
        # write GoDaddy keys file
        file_path = os.path.join(self._base_dir, 'le-godaddy-dns', 'keys')
        if os.path.isfile(file_path):
            if input('Replace GoDaddy key file? (y/n): ').lower() == 'y':
                self.logger.info('rewriting GoDaddy key file')
                self.write_godaddy_keys(file_path)
        else:
            self.write_godaddy_keys(file_path)

        # write dehydrated domains.txt file
        file_path_1 = os.path.join(self._base_dir, 'dehydrated', 'domains.txt')
        file_path_2 = os.path.join(self._base_dir, 'domains.txt')

        if os.path.isfile(file_path_1):
            if input('Add new domains to certificate list? (y/n): ').lower() == 'y':
                self.query_utm()
                self.write_domains_file(file_path_1, file_path_2)
                self.write_domain_directories()
        else:
            self.query_utm()
            self.write_domains_file(file_path_1, file_path_2)
            self.write_domain_directories()

        return True

    def query_utm(self):

        ca_grep = "'ref' => 'REF_Ca"
        bad_chars = "',"
        rgx = re.compile('[%s]' % bad_chars)
        cc_command = '/usr/local/bin/confd-client.plx  get_objects ca host_key_cert'

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.logger.info('connecting to UTM')
        self.logger.debug('connecting to UTM at: {0} using key file: {1}'.format(self._host, self._key))
        ssh.connect(self._host, username='root', key_filename=self._key)

        self.logger.info('Querying for current certificates')
        self.logger.debug('executing: {0}'.format(cc_command))
        stdin, stdout, stderr = ssh.exec_command(cc_command)

        for line in stdout.readlines():
            if ca_grep in line:
                cert_name = rgx.sub('', line.split()[2])
                self._domains[cert_name] = input('Enter domain for certificate {0}: '.format(cert_name))
        return True

    def write_domains_file(self, file_one, file_two):

        length = len(self._domains)
        record = 1
        self.logger.info('writing domains file for dehydrated script')
        self.logger.debug('writing file at: {0}'.format(file_one))
        with open(file_one, 'w') as output:
            for domain in self._domains:
                if length != record:
                    output.write('{0}\n'.format(self._domains[domain]))
                else:
                    output.write(self._domains[domain])
                record += 1

        self.logger.info('writing domain and cert references for update-cert.py')
        self.logger.debug('writing file at: {0}'.format(file_two))
        out_dict = dict(domains=self._domains, host=self._host, key=self._key)
        with open(file_two, 'w') as output:
            json.dump(out_dict, output)

    def write_godaddy_keys(self, path):

        self.logger.info('writing GoDaddy key file')
        self.logger.debug('writing file at: {0}'.format(path))
        with open(path, 'w') as output:
            output.write('[go_daddy]\n')
            output.write('api_key = {0}\n'.format(input('GoDaddy API Key: ')))
            output.write('api_secret = {0}'.format(input('GoDaddy API Secret: ')))
            output.close()

    def write_domain_directories(self):

        self.logger.info('transferring update-cert.py')
        cmd = 'if [ ! -d "/root/.getssl" ]; then mkdir /root/.getssl; fi'
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self._host, username='root', key_filename=self._key)
        self.logger.debug('creating .getssl directory if not present using: {0}'.format(cmd))
        ssh.exec_command(cmd)
        self.logger.debug('transferring update-cert.py to /root/.getssl/update-cert.py')
        scp = SCPClient(ssh.get_transport())
        scp.put(os.path.join(self._base_dir, 'update-cert.py'),
                os.path.join('/root', '.getssl', 'update-cert.py'))

        self.logger.info('creating directories to store certificates on UTM')
        for domain in self._domains:
            cmd = 'if [ ! -d "/root/.getssl/{0}" ]; then mkdir /root/.getssl/{0}; fi'.format(self._domains[domain])
            self.logger.debug('executing command: {0}'.format(cmd))
            ssh.exec_command(cmd)


class Cron():
    def __init__(self, base, logger=None):

        self._base_dir = base
        inpath = os.path.join(self._base_dir,'domains.txt')
        self.logger = logger or logging.getLogger(__name__)

        # load domains and cert names collected during setup
        self.logger.info('loading settings from file')
        self.logger.debug('using file: {0}'.format(inpath))
        with open(inpath) as infile:
            data = json.load(infile)
            self._domains = data['domains']
            self._host = data['host']
            self._key = data['key']

    def daily_job(self):

        cmd = '{0} -k {1} -c'.format(os.path.join(self._base_dir, 'dehydrated', 'dehydrated'),
                                     os.path.join(self._base_dir, 'godaddy.py'))

        self.logger.info('running dehydrated script')
        self.logger.debug('using command: {0}'.format(cmd))

        with subprocess.Popen(cmd.split(), stdout=subprocess.PIPE,
                              bufsize=1, universal_newlines=True) as proc, StringIO() as buf:
            for line in proc.stdout:
                buf.write(line)
                self.logger.info(line.rstrip('\n'))
        rc = proc.returncode
        self.logger.info('dehydrated script complete')

    def deploy_hook(self, domain):

        # retrieve certificate reference from dictionary of domains and cert references
        for r, d in self._domains.items():
            if d == domain:
                ref = r

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self._host, username='root', key_filename=self._key)
        scp = SCPClient(ssh.get_transport())

        self.logger.info('transferring certificate and private key for {0}'.format(domain))

        source_file = os.path.join(self._base_dir, 'dehydrated', 'certs', domain, 'fullchain.pem')
        dest_file = os.path.join('/', 'root', '.getssl', domain, domain + '.crt')
        self.logger.debug('transferring file {0} to {1}'.format(source_file, dest_file))
        scp.put(source_file, dest_file)

        source_file = os.path.join(self._base_dir, 'dehydrated', 'certs', domain, 'privkey.pem')
        dest_file = os.path.join('/', 'root', '.getssl', domain, domain + '.key')
        self.logger.debug('transferring file {0} to {1}'.format(source_file, dest_file))
        scp.put(source_file, dest_file)

        self.logger.info('running update-cert.py on UTM for {0}'.format(domain))
        cmd = 'python /root/.getssl/update-cert.py {0} {1}'.format(domain, ref)
        self.logger.info('executing command "{0}" on UTM'.format(cmd))
        print('executing command "{0}" on UTM'.format(cmd))
        ssh.exec_command(cmd)
        sleep(5)
        ssh.close()


if __name__ == '__main__':
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    LOG_FILE = 'lesophos.log'

    parser = argparse.ArgumentParser()
    parser.add_argument('operation',
                        help='setup or cron')
    parser.add_argument('-u', '--utm',
                        help='IP address of Sophos UTM')
    parser.add_argument('-k', '--key',
                        default=os.path.expanduser('~/.ssh/id_rsa'),
                        help='path to SSH private key, defaults to "~/.ssh/id_rsa"')
    parser.add_argument('-d', '--debug',
                        default=logging.INFO,
                        action="store_const", dest='loglevel', const=logging.DEBUG,
                        help="Switch logging level from INFO to DEBUG")
    args = parser.parse_args()

    logger = logging.getLogger(__name__)
    logger.setLevel(args.loglevel)
    # create a file handler
    handler = logging.FileHandler(os.path.join(BASE_DIR, LOG_FILE))
    handler.setLevel(args.loglevel)
    # create a logging format
    formatter = logging.Formatter('%(asctime)s - %(module)s - %(funcName)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    # add the handlers to the logger
    logger.addHandler(handler)

    if args.operation == 'cron':
        logger.info('lesophos started in cron mode')
        instance = Cron(BASE_DIR)
        instance.daily_job()
    else:
        logger.info('lesophos started in setup mode')
        instance = SetupEnvironment(BASE_DIR, args.utm, args.key)
        instance.setup()