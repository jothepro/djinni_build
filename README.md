# djinni_build.py 🦎

Script to package and distribute Djinni libraries easily.

## Requirements

- A project structure close to [jothepro/djinni-library-template](https://github.com/jothepro/djinni-library-template)
- Should be used together with [jothepro/djinni-cmake](https://github.com/jothepro/djinni-cmake).


## What it does

This build script automates the building & packaging for Djinni libraries.

It supports these platforms:

- Android (AAR)
- iOS (xcframework, Swiftpackage)
- macOS (xcframework, Swiftpackage)
- Windows (NuGet package)
- Linux (just Conan)

The script provides a CLI that allows the user to configure what the output should be.

The user is able to configure:

- What target platform to build for (Android, iOS, macOS, Windows, Linux)
- Which architectures to build for (x86, x86_64, armv7, armv8)
- Wether and how to package the resulting binaries (AAR, NuGet, XCFramework, Swift Package)
- Wether to build documentation for the library interfaces in each target language (Java, Objective-C, C++/CLI)

For every target language, the following steps are executed (if requested by the user):

- **Configure Project & Install dependencies**: Runs `conan install` for each target architecture & target platform
  to configure the CMake project and install all dependencies defined in the Conanfile.
- **Build**: Runs `conan build` for each target architecture & platform
- **Package**: Executes the platform specific packaging tasks. In some cases the packages will be built outside the
  build directory, but the results will be copied there once finished.
- **Render documentation**: For each target language a Doxyfile has to be provided in the root of the project
  (`Doxyfile-Cpp`, `Doxyfile-CppCli`, `Doxyfile-Java`, `Doxyfile-ObjC`). Doxygen will be called for all languages that
  the build was executed for (e.g.: Android -> Java, iOS -> ObjC, Windows -> C++/CLI). The C++-Documentation will always
  be created.


## How to use

To use the script, include this repository as submodule in your Djinni library project:

```bash
git submodule add https://github.com/jothepro/djinni_build.git
```

Import `djinni_build.py` and configure the project structure:

```python3
#!/usr/bin/env python3

import os
from djinni_build.djinni_build import DjinniBuild

workdir = os.getcwd()
djinniBuild = DjinniBuild(
    working_directory=workdir,
    darwin_target='MyDjinniLibrary',
    darwin_target_dir=f'lib/platform/darwin',
    windows_target='MyDjinniLibrary',
    windows_target_dir=f'lib/platform/windows',
    android_target='MyDjinniLibrary',
    android_target_dir=f'lib/platform/android',
    version='v1.0.0',
    android_profile=f'{workdir}/conan/profiles/android',
    macos_profile=f'{workdir}/conan/profiles/macos',
    ios_profile=f'{workdir}/conan/profiles/ios',
    windows_profile=f'{workdir}/conan/profiles/windows',
    linux_profile=f'{workdir}/conan/profiles/linux',
    android_project_dir=f'{workdir}/lib/platform/android',
    android_module_name=f'MyDjinniLibrary',
    nupkg_dir=f'{workdir}/lib/platform/windows',
    nupkg_name='MyDjinniLibrary',
    swiftpackage_dir=f'{workdir}/lib/platform/darwin'
)
djinniBuild.main()
```

In it's current state not everything in the script is configurable and heavily relies on conventions.
This is why it is recommende to strictly stick with the project structure of [jothepro/djinni-library-template](https://github.com/jothepro/djinni-library-template)
to avoid compatibility issues!

## CLI Interface

This example output from the CLI shows what the configuration options are:

```
usage: build.py [-h] [--configuration {release,debug}] [--android [{x86_64,x86,armv8,armv7} ...]] [--macos [{armv8,x86_64} ...]] [--iphonesimulator [{armv8,x86_64} ...]]
                [--iphoneos [{armv8,armv7} ...]] [--windows [{x86_64,x86,armv8,armv7} ...]] [--linux [{x86_64,x86,armv8,armv7} ...]] [--build-directory BUILD_DIRECTORY] [--android-ndk ANDROID_NDK]
                [--java-8-home JAVA_8_HOME] [--java-11-home JAVA_11_HOME] [--package [{xcframework,swiftpackage,conan,aar,nuget} ...]] [--render-docs] [--clean]

Build & package library for different platforms

optional arguments:
  -h, --help            show this help message and exit
  --configuration {release,debug}
  --android [{x86_64,x86,armv8,armv7} ...]
                        list of architectures that the library should be built for android
  --macos [{armv8,x86_64} ...]
  --iphonesimulator [{armv8,x86_64} ...]
  --iphoneos [{armv8,armv7} ...]
  --windows [{x86_64,x86,armv8,armv7} ...]
                        list of architectures to build for windows
  --linux [{x86_64,x86,armv8,armv7} ...]
                        list of architectures to build for linux
  --build-directory BUILD_DIRECTORY
  --android-ndk ANDROID_NDK
                        directory of the NDK installation
  --java-8-home JAVA_8_HOME
                        JAVA_HOME for a Java 1.8 installation. Required if building for Android
  --java-11-home JAVA_11_HOME
                        JAVA_HOME for a Java Version > 11. Required if building for Android
  --package [{xcframework,swiftpackage,conan,aar,nuget} ...]
                        which packages to create. Packages that cannot be created for the selected target architectures will be ignored.
  --render-docs         render doxygen documentation for the languages of the selected target platforms
  --clean               clean all build artifacts outside of the build folder, that this script may have created
```