from setuptools import find_packages, setup

package_name = "scout_lio_support"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml", "README.md"]),
    ],
    install_requires=["setuptools", "numpy"],
    zip_safe=True,
    maintainer="Scout maintainers",
    maintainer_email="maintainer@example.com",
    description="Validated RoboSense XYZIRT conversion for Scout LIO-SAM",
    license="BSD-3-Clause",
    entry_points={"console_scripts": [
        "robosense_to_lio = scout_lio_support.robosense_to_lio:main",
    ]},
)
