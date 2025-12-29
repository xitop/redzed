============
Installation
============

Prerequisites
=============

Redzed needs Python 3.11 or newer. No 3\ :sup:`rd` party libraries are required.

Unit tests require ``pytest`` with the ``pytest-asyncio`` and ``pytest-xdist`` plugins.

Redzed was developed, tested and deployed on Linux systems only.
We hope it runs also on Windows, but we don't know. If you can install
it on Windows and run the unit tests, please report the result.


Installing
==========

We recommend using a virtual environment. If you don't want a virtual
environment, consider an installation to user's local directory with
the ``--user`` option.

Install from PyPi with::

  python3 -m pip install --upgrade redzed

Alternatively install from github repository with::

  python3 -m pip install --upgrade git+https://github.com/xitop/redzed.git
