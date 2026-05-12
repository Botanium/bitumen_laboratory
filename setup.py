from setuptools import find_packages, setup

from bitumen_laboratory import __version__ as version


setup(
	name="bitumen_laboratory",
	version=version,
	description="Laboratory module for Bitumen factory truck tests",
	author="Botanium",
	author_email="botan.b.abdullah@gmail.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
)

