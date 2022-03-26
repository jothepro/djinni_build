from setuptools import setup

# reading long description from file
with open('README.md', 'r', encoding='utf-8') as file:
    long_description = file.read()

setup(name='djinni_build',
      setuptools_git_versioning={
          "enabled": True,
      },
      setup_requires=["setuptools-git-versioning"],
      description='Utility to package and distribute Djinni libraries easily.',
      long_description=long_description,
      long_description_content_type='text/markdown',
      url='https://github.com/jothepro/djinni_build',
      author='jothepro',
      author_email='djinni_build@jothe.pro',
      license='MIT',
      packages=['djinni_build'],
      classifiers=[
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.10'
      ],
      python_requires='>=3.10',
      install_requires=['conan>=1.44'],
      keywords='djinni')
