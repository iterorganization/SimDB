import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="simdb",
    version="0.1.0",
    author="Jonathan Hollocombe",
    author_email="jonathan.hollocombe@ukaea.uk",
    description="ITER Simulation Management Tool",
    long_description=long_description,
    url="https://git.iter.org/projects/IMEX/repos/simdb/browse",
    packages=setuptools.find_packages(where='src'),
    package_dir={'': 'src'},
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
    ],
    license="See LICENCE.txt",
    install_requires=[
        "argcomplete (>= 1.9.4)",
        "numpy (>= 1.14)",
        "python-dateutil (>= 2.6)",
        "pyyaml (>= 3.13)",
        "requests (>= 2.19.1)",
        "sqlalchemy (>= 1.2.12)",
        "urllib3 (>= 1.23)",
        "appdirs (>=1.4.0)",
        "uri (>=2.0)",
        "email-validator (>=1.1)",
        "semantic-version (>=2.8)",
        "click (>=7.0)",
        "Cerberus (>=1.3.2)",
        "distro (>=1.5.0)",
        "PyJWT (>=1.4.0)",
    ],
    scripts=[
        "scripts/simdb",
        "scripts/simdb_server",
    ],
    package_data={
        "simdb": ["LICENCE.txt"],
        "simdb.cli": ["template.yaml"],
        "simdb.remote": ["simdb.initd", "simdb.nginx"],
    },
    python_requires='>=3.6',
)
