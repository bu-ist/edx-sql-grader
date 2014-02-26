from setuptools import setup

setup(
    name="edX SQL Grader",
    version="0.1",
    install_requires=['distribute'],
    requires=[],
    packages=[
        "graders",
        "util"
    ],
)
