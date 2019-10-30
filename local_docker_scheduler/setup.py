import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="local-docker-scheduler",
    version="0.0.2",
    author="Dessa",
    author_email="engineering@dessa.com",
    description="Local Scheduler",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/DeepLearnI/local-docker-scheduler",
    packages=setuptools.find_packages(),
    classifiers=[ ],
    python_requires='>=3.6',
)