from setuptools import setup, find_packages

setup(
    name='multitidal',
    packages=find_packages(),
    setup_requires=[
        'pycodestyle==2.5.0',
        'pytest-runner',
        'pytest-pylint',
        'pytest-codestyle',
        'pytest-flake8==1.0.4',
        'pytest-mypy',
    ],
    tests_require=['pytest'],
)
