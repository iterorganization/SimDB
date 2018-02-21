from distutils.core import setup

setup(
    name="simdb",
    version="0.1.0",
    description="ITER Simulataion Management Tool",
    author="Jonathan Hollocombe",
    author_email="jonathan.hollocombe@ukaea.uk",
    url="https://git.iter.org/projects/IMEX/repos/simulation-management/browse",
    packages=["simdb", "simdb.cli", "simdb.database"],
    license="See LICENCE.txt",
    requires=[
        "PyYAML (>= 3.12)",
        "SqlAlchemy (>= 1.2.2)",
        "argcomplete (>= 1.9.4)",
        "dateutil (>= 2.6.1)",
        "requests (>= 2.18.4)",
    ],
    scripts=["scripts/simdb"],
    package_data={
        "simdb": ["LICENCE.txt"],
        "simdb.cli": ["template.yaml"],
    },
)
