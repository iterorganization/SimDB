from distutils.core import setup

setup(
    name="simdb",
    version="0.1.0",
    description="ITER Simulation Management Tool",
    author="Jonathan Hollocombe",
    author_email="jonathan.hollocombe@ukaea.uk",
    url="https://git.iter.org/projects/IMEX/repos/simulation-management/browse",
    packages=["simdb", "simdb.cli", "simdb.database", "simdb.config"],
    license="See LICENCE.txt",
    install_requires=[
        "argcomplete (>= 1.9.4)",
        "numpy (>= 1.15.3)",
        "python-dateutil (>= 2.7.3)",
        "pyyaml (>= 3.13)",
        "requests (>= 2.19.1)",
        "sqlalchemy (>= 1.2.12)",
        "urllib3 (>= 1.23)",
    ],
    scripts=["scripts/simdb"],
    package_data={
        "simdb": ["LICENCE.txt"],
        "simdb.cli": ["template.yaml"],
    },
)
