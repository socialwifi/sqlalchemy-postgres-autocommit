import pathlib

import pkg_resources

from setuptools import find_packages
from setuptools import setup

with pathlib.Path('base_requirements.txt').open() as requirements_txt:
    install_requires = [
        str(requirement) for requirement in pkg_resources.parse_requirements(requirements_txt)
    ]


setup(
    name='sqlalchemy-postgres-autocommit',
    version='0.4.2.dev0',
    description='A library to use SQLAlchemy with PostgreSQL in an autocommit mode.',
    author='Jakub Gocławski',
    author_email='it@socialwifi.com',
    url='https://github.com/socialwifi/sqlalchemy-postgres-autocommit',
    packages=find_packages(exclude=['tests']),
    install_requires=install_requires,
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
    license='BSD',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ]
)
