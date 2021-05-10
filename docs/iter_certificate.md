# Installing ITER SSL certificate

To use the SimDB CLI on an ITER HPC node, you need to first download the root and issuing CA certificates:

```bash
wget "http://pki.iter.org/CertEnroll/io-ws-pkiroot_ITER%20Organization%20Root%20CA.crt"
wget "http://pki.iter.org/CertEnroll/io-ws-pki1.iter.org_ITER%20Organization%20Issuing%20CA1.crt"
```

The certificates need to be converted into the PEM format and concatenated into a single file, in this case stored at `$HOME/iter.pem`:

```bash
openssl x509 -inform DEM -in io-ws-pki1.iter.org_ITER\ Organization\ Issuing\ CA1.crt -out CA1.pem
openssl x509 -inform DEM -in io-ws-pkiroot_ITER\ Organization\ Root\ CA.crt -out CA2.pem
cat CA1.pem CA2.pem > $HOME/iter.pem
```

Before using the SimDB client you need to set the environment variable `REQUESTS_CA_BUNDLE` to point to the file created above:

```bash
export REQUESTS_CA_BUNDLE=$HOME/iter.pem
```

This line can be added to `$HOME/.bash_profile` so that you don't need to set it for each bash terminal. 