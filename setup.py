import os
from distutils.core import setup

def find_packages():
    r = []
    for dir, dns, fns in os.walk('appy'):
        if '.svn' in dir: continue
        package_name = dir.replace('/', '.')
        r.append(package_name)
    return r

setup(name="appy",
      version="1.99.dev0",
      description="The Appy framework",
      long_description="Appy builds simple but complex web Python apps.",
      author="Gaetan Delannay",
      author_email="gaetan.delannay AT geezteem.com",
      license="GPL",
      platforms="all",
      url='http://appyframework.org',
      packages=find_packages(),
      package_data={'': ["*.*"]})
