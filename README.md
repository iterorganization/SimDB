# SimDB simulation management tool

SimDB is a tool designed to track, manage, upload and query simulations. The simulation data can be tagged with metadata, managed locally or transferred to remote SimDB services. Uploaded simulations can then be queried based on metadata.

## Command line interface

SimDB consists of a command line interface (CLI) tool which interacts with one or more remote services.

For details on how to install the CLI see [here](https://simdb.readthedocs.io/en/stable/install_guide.html) and for information on how to use the CLI see [here](https://simdb.readthedocs.io/en/stable/user_guide.html).

### Accessing ITER remotes

To access data from the ITER remotes from outside of the ITER systems you'll need to [add and configure a SimDB remote](https://simdb.readthedocs.io/en/stable/iter_remotes.html).

### Installing ITER certificate

To access the ITER remote from within the ITER systems you will need to install the ITER SSL certificate. Details for how to do this can be found [here](https://simdb.readthedocs.io/en/stable/iter_certificate.html).

## Server setup

For information on setting and maintaining a remote CLI server see [here](https://simdb.readthedocs.io/en/stable/maintenance_guide.html).

## Developer guide

Information about setting up a developer environment can be found [here](https://simdb.readthedocs.io/en/stable/developer_guide.html).
