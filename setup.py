from setuptools import setup

setup(
    name="edX SQL Grader",
    version="0.1",
    install_requires=[
        'requests',
        'path.py',
        'python-daemon'
        ],
    packages=[
        "graders",
        "xqueue"
    ]
)
