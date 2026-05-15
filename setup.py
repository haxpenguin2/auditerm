from setuptools import setup, find_packages

setup(
    name="auditerm",
    version="0.1.0",
    description="A modern terminal audio player with TUI file browser and visualizer",
    author="you",
    packages=find_packages(),
    install_requires=[
        "pygame",
        "mutagen",
        "numpy",
    ],
    entry_points={
        "console_scripts": [
            "auditerm=auditerm.main:main",
        ],
    },
    python_requires=">=3.8",
)
