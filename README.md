# djinni_build.py 🦎

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/jothepro/djinni_build)](https://github.com/jothepro/djinni_build/releases/latest)
[![GitHub](https://img.shields.io/github/license/jothepro/djinni_build)](https://github.com/jothepro/djinni_build/blob/main/LICENSE)
![PyPI - Downloads](https://img.shields.io/pypi/dm/djinni_build)

Utility to package and distribute Djinni libraries easily.

## Requirements

- A project structure close to [jothepro/djinni-library-template](https://github.com/jothepro/djinni-library-template)
- Should be used together with [jothepro/djinni-cmake](https://github.com/jothepro/djinni-cmake).
- Python >= 3.10


## What it does

This utility automates the building & packaging for Djinni libraries.

It supports these platforms:

- Android (AAR)
- iOS (xcframework, Swiftpackage)
- macOS (xcframework, Swiftpackage)
- Windows (NuGet .NET package)
- Linux (Conan)

[`DjinniBuild`](djinni_build/djinni_build.py) provides a CLI that allows the user to configure what the output should be.

The user is able to configure:

- What target platform to build for (Android, iOS, macOS, Windows, Linux)
- Which architectures to build for (x86, x86_64, armv7, armv8)
- How to package the resulting binaries (AAR, NuGet, XCFramework, Swift Package, Conan)

For every target language, the following steps are executed:

- **Configure Project & Install Dependencies**: Runs `conan install` for each target architecture & target platform
  to configure the CMake project and install all dependencies defined in the Conanfile.
- **Build**: Runs `conan build` for each requested target architecture & platform
- **Package**: Executes the platform specific packaging tasks.


## How to use

Install `djinni_build` from PYPi:

```bash
pip install djinni_build
```

Then import `DjinniBuild` and configure the project structure and then execute the `main()` function:

```python3
#!/usr/bin/env python3

from djinni_build import DjinniBuild

djinniBuild = DjinniBuild(
  darwin_target='MyDjinniLibrary',
  windows_target='MyDjinniLibrary',
  android_target='MyDjinniLibrary',
  android_module_name='MyDjinniLibrary',
  nupkg_name='MyDjinniLibrary',
  conan_user='jothepro',
  conan_channel='release'
)
djinniBuild.main()
```

In its current state not everything in the script is configurable and some things will only work if the correct
directory structures and files are present.
It is recommended to strictly stick with the project structure of [jothepro/djinni-library-template](https://github.com/jothepro/djinni-library-template)
to avoid compatibility issues!

## CLI Interface

This example output from the CLI shows what the configuration options for the user are:

```
usage: build.py [-h] [--configuration {release,debug}] [--android [{x86_64,x86,armv8,armv7} ...]] [--macos [{armv8,x86_64} ...]]
                [--iphonesimulator [{armv8,x86_64} ...]] [--iphoneos [{armv8,armv7} ...]] [--windows [{x86_64,x86,armv8,armv7} ...]]
                [--linux [{x86_64,x86,armv8,armv7} ...]] [--build-directory BUILD_DIRECTORY] [--build-profile CONAN_BUILD_PROFILE]
                [--package [{xcframework,swiftpackage,conan,aar,nuget} ...]]

Build & package library for different platforms

options:
  -h, --help            show this help message and exit
  --configuration {release,debug}
  --android [{x86_64,x86,armv8,armv7} ...]
                        list of architectures that the library should be built for android
  --macos [{armv8,x86_64} ...]
                        list of architectures to build for macOS
  --iphonesimulator [{armv8,x86_64} ...]
                        list of architectures to build for the iOS Simulator
  --iphoneos [{armv8,armv7} ...]
                        list of architectures to build for iOS
  --windows [{x86_64,x86,armv8,armv7} ...]
                        list of architectures to build for windows
  --linux [{x86_64,x86,armv8,armv7} ...]
                        list of architectures to build for linux
  --build-directory BUILD_DIRECTORY
  --build-profile CONAN_BUILD_PROFILE
  --package [{xcframework,swiftpackage,conan,aar,nuget} ...]
                        which packages to create. Packages that cannot be created for the selected target platforms will be ignored.
```