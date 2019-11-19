import os
from distutils.core import setup

def find_packages():
    r = []
    for dir, dns, fns in os.walk('appy'):
        if '.svn' in dir: continue
        package_name = dir.replace('/', '.')
        r.append(package_name)
    return r

setup(name="appy-python-3",
      version="2019.11.19",
      description="The Appy framework (Python 3)",
      long_description="Unofficial pypi release of offical code from https://forge.pallavi.be/projects/appy-python-3.",
      author="Gaetan Delannay",
      author_email="gaetan.delannay@geezteem.com",
      license="GPL",
      platforms="all",
      url='http://appyframework.org',
      packages=find_packages(),
      package_data={'': ["*.*"]})
