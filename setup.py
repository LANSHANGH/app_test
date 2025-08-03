# setup.py
from setuptools import setup
from Cython.Build import cythonize

# 我们要将 secure_core.py 编译成一个二进制模块
setup(
    ext_modules=cythonize("secure_core.py")
)
