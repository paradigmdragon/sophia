from setuptools import setup, find_packages

setup(
    name="sophia-core",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "faster-whisper>=0.10.0",
        "ffmpeg-python>=0.2.0",
        "click>=8.1.0",
        "requests>=2.31.0",
        "pydantic>=2.0.0"
    ],
)
