from setuptools import setup, find_packages

setup(
    name="multitidal",
    packages=find_packages(),
    setup_requires=[
        "pytest-runner==5.3.1",
        "pytest-pylint==0.18.0",
        "pytest-mypy==0.8.1",
        "pytest-black==0.3.12",
    ],
    install_requires=[
        "tornado==6.0.3",
        "docker==4.1.0",
    ],
    tests_require=["pytest"],
    include_package_data=True,
)
