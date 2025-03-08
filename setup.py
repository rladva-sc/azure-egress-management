import os
from setuptools import setup, find_packages

# Read the long description from the README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements from requirements.txt
with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = f.read().splitlines()

setup(
    name="azure-egress-management",
    version="0.1.0",  # This will be dynamically updated by the publish workflow
    author="Azure Egress Management Team",
    author_email="maintainer@example.com",
    description="A tool for monitoring and optimizing Azure egress traffic",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/username/azure-egress-management",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Developers",
        "Topic :: System :: Monitoring",
        "Topic :: System :: Networking :: Monitoring",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "azure-egress=src.cli:app",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
