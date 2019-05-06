from distutils.core import setup
from setuptools import find_packages

pkgs = find_packages()
install_requires = [
    "vnpy>2", "flask"
]
setup(name='ctpbee',
      version='0.11',
      author='somewheve',
      author_email='somewheve@gmail.com',
      description="easy ctp trade and market support",
      url='https://github.com/somewheve/ctpbee',
      license="MIT",
      packages=pkgs,
      install_requires=install_requires,
      )
