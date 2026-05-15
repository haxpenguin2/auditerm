from setuptools import setup, find_packages

setup(
    name="auditerm",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pygame-ce",
        "mutagen",
        "numpy",
    ],
    entry_points={
        "console_scripts": [
            "auditerm=auditerm.main:main",
        ],
    },
)
