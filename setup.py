from setuptools import setup

setup(
    name="multitidal",
    packages=[
        "multitidal",
    ],
    setup_requires=[
        "pytest-runner",
        "pytest-pylint",
        "pytest-flake8==1.0.4",
        "pytest-mypy",
    ],
    install_requires=[
        "tornado==6.0.3",
        "docker==4.1.0",
    ],
    tests_require=["pytest"],
    include_package_data=True,
)
