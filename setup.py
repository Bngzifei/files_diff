# coding=utf-8

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name='file-diff',
    version="1.0.4",
    description=(
        'Specifies the tool for text content difference detection in the directory'
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='zifeiyushui8',
    author_email='bngzifei@gmail.com',
    maintainer='zifeiyushui8',
    maintainer_email='bngzifei@gmail.com',
    license='MIT License',
    packages=find_packages(),
    platforms=["all"],
    include_package_data=True,
    url='https://github.com/Bngzifei/files_diff.git',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Operating System :: OS Independent',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: Implementation',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Software Development :: Libraries'
    ],
    install_requires=[]
)