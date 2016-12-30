# lésophos

A script used to automate the creation, DNS verification, and installation of Let's Encrypt certificates on a Sophos UTM.  Lésophos builds on the sophos-utm-letsencrypt script by automating the process but as a result requires Python 3 which is not included as part of the UTM operating system.
The script is made possible by the following projects:

* [dehydrated](https://github.com/lukas2511/dehydrated)
* [le-godaddy-dns](https://github.com/josteink/le-godaddy-dns)
* [sophos-utm-letsencrypt](https://github.com/rklomp/sophos-utm-letsencrypt)

## Prerequisites
* A linux system with Python 3 on the same network as the UTM with the ability to connect as root using [public key authentication](http://www.virtualizationhowto.com/2016/01/sophos-utm-setup-public-key-authentication-root/) to the UTM
* [Production Godaddy API keys](https://developer.godaddy.com/keys/)
* Install Verification CA Certificate

    * Download the let's encrypt intermediate [certificate](https://letsencrypt.org/certs/lets-encrypt-x3-cross-signed.pem)
    * Install it as Verification CA via webadmin (Webserver Protection -> Certificate Management -> Certificate Authority -> New CA...)
    * I have named it "Let’s Encrypt X3", but you can give it any name you want.  This certificate is then served by the Web Application Firewall when a Let's Encrypt certificate is used to complete the certificate chain and provide better acceptance of the Let's Encrypt certificate.
* Each virtual webserver must have an existing certificate assigned to it before utilizing lésophos
    * Use an existing certificate entry to overwrite, or generate a new one in the webgui (Webserver Protection -> Certificate Management -> Add Certificate...). Using the VPN ID type "Hostname". Assign this certificate to your virtual webserver.


## Setup
* Setup takes two parameters:
    * one required parameter, **'u'**, the IP address of your UTM
    * one optional parameter, **'k'**, the path to the appropriate key file to use when connecting to the UTM via SSH as root.

    ```python3 lesophos.py setup -u 192.168.1.1 -k /home/johndoe/.ssh/id_rsa```

* The script will prompt you for your Godaddy API key and secret which will be saved in a file named keys

* The script will display each certificate reference retrieved from the UTM and prompt you for the associated full domain
    * _example:_ REF_CaHosMedia is associated with media.xyz.com

* The script will generate all configuration files and the appropriate directory structure will be created on the UTM to receive the generated certificates and private keys

* Generate your initial certificates by running lésophos again in cron mode.  Domain ownership will be verified by temporarily modifying your DNS records with a challenge key, once ownership is verified the certificates will be generated and installed on your UTM.  All activity will be logged to lesophos.log in the same directory as the script.

    ```python3 lesophos.py cron```

* Create a daily cron job utilizing your account to run the above command making sure to include the full path to the script.  This will check the each certificate's status daily and replace with a new one as needed
    * _example cron edit command:_ ```crontab -u user1 -e```
    * _example cron entry to run everyday at 3 AM:_ ``` 00 3 * * * python3 /home/user1/lesophos/lesophos.py cron```

* The setup command can be rerun at any time to modify your Godaddy keys or list of domains to generate certificates for

**Lets Encrypt limits the amount of certificates issued to one domain to 5 per week.  Uncommenting line 20 of _dehydrated\config_ will utilize the staging certificate authority instead of the production certificate authority.  It's advised to utilize the staging CA until everything is verified as functioning correctly and you see the invalid certificates being presented when browsing to webservers protected by your UTM.**