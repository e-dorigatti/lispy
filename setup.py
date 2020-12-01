from setuptools import find_packages, setup


def main():
    with open('README.md', encoding='utf-8') as f:
        long_description = f.read()

    setup(
        name='LisPy',
        version='0.1.0',
        license='', # TODO license
        description='Python-based LISP interpreter',
        long_description=long_description,
        author='Emilio Dorigatti',
        author_email='emilio.dorigatti@gmail.com',
        url='https://github.com/e-dorigatti/lispy',
        packages=find_packages(),
        install_requires=[
            'click',
            'prompt-toolkit'
        ],
        tests_require=['pytest'],
        entry_points={'console_scripts': ['lispy=lispy.cli:main']},
    )


if __name__ == '__main__':
    main()
