from setuptools import setup

setup(
    name = 'tracermppt',
    py_modules = ['tracermppt'],
    version = '0.3',
    description = 'Interface for controlling and interrogating the '
        'Tracer-2210RN and similar charge cotnrollers via the remote '
        'monitoring port',
    author = 'Brian Mayton',
    author_email = 'bmayton@media.mit.edu',
    license = 'MIT',
    url = 'https://github.com/bmayton/tracermppt',
    download_url = 'https://github.com/bmayton/tracermppt/tarball/0.3',
    keywords = [],
    classifiers = [],
    install_requires = [
        "enum34",
        "pyserial",
    ]
)
