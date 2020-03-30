from setuptools import setup, find_packages

setup(name="diffkemp-htmlgen",
      version="0.1",
      description="A tool that converts DiffKemp YAML output into human-readable HTML.",
      author="Tomas Glozar",
      author_email="tglozar@gmail.com",
      url="https://github.com/lenticularis39/diffkemp-htmlgen",
      packages=find_packages(),
      install_requires=["pyyaml", "yattag"])
