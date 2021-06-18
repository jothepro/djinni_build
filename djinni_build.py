#!/usr/bin/env python3

import argparse
import os
import sys
from enum import Enum
from collections import namedtuple
from conans.client.conan_api import Conan
from string import Template
import shutil

print_prefix = "[djinni-build.py]"


class ArgparseEnum(Enum):

    def __str__(self):
        return self.name

    @classmethod
    def from_string(cls, string: str):
        """this is required for the enum to work with argparse"""
        try:
            return cls[string]
        except KeyError:
            raise ValueError()


ArchitectureDetails = namedtuple('ArchitectureName', 'conan android windows bit')


class Architecture(ArgparseEnum):
    """enum with all possible architectures that one can build for, and the names for them on each target platform"""
    x86_64 = ArchitectureDetails(conan='x86_64', android='x86_64', windows='win10-x64', bit='64')
    x86 = ArchitectureDetails(conan='x86', android='x86', windows='win10-x86', bit='32')
    armv8 = ArchitectureDetails(conan='armv8', android='arm64-v8a', windows='win10-arm64', bit='64')
    armv7 = ArchitectureDetails(conan='armv7', android='armeabi-v7a', windows='win10-arm', bit='32')


class BuildConfiguration(ArgparseEnum):
    """enum of all possible build configurations."""
    release = 'Release'
    debug = 'Debug'


class BuildContext:
    """Base class for all build contexts. Contains common code that is shared between builds for different
    languages/platforms """

    def __init__(self, conan: Conan, working_directory: str, target: str, version: str, build_directory: str,
                 profile: str, architectures: [Architecture],
                 configuration: BuildConfiguration, env: list[str] = [], settings: list[str] = []):
        self.conan = conan
        self.working_directory = working_directory
        self.target = target
        self.version = version
        self.profile = profile
        self.build_directory = build_directory
        self.architectures = architectures
        self.configuration = configuration
        self.env = ['CONAN_RUN_TESTS=False'] + env
        self.settings = [f'build_type={self.configuration.value}'] + settings

    def build(self):
        """builds all selected architectures"""
        for architecture in self.architectures:
            print(f'{print_prefix} building for architecture {architecture.name}:')
            self.conan.build(conanfile_path=self.working_directory,
                             build_folder=f"{self.build_directory}/{architecture.value.conan}")

    def conan_install(self, architecture: Architecture, settings: list[str] = [],
                      env: list[str] = []):
        """installs all conan dependencies defined in conanfile.py"""
        print(f'{print_prefix} installing dependencies for architecture {architecture.name}:')
        all_settings = settings + self.settings + [f"arch={architecture.value.conan}"]
        all_env = env + self.env
        self.conan.install(install_folder=f"{self.build_directory}/{architecture.value.conan}",
                           profile_names=[self.profile], build=["missing"],
                           settings=all_settings,
                           env=all_env)

    def conan_create(self, architecture: Architecture, settings: list[str] = [],
                     env: list[str] = []):
        """creates the conan package for the current configuration"""
        print(f'{print_prefix} creating conan package for architecture {architecture.name}:')
        all_settings = settings + self.settings + [f"arch={architecture.value.conan}"]
        all_env = env + self.env
        self.conan.create(profile_names=[self.profile],
                          conanfile_path=self.working_directory,
                          settings=all_settings,
                          env=all_env)

    @staticmethod
    def render_doxygen_docs(doxyfile: str):
        """calls doxygen with the given Doxyfile."""
        print(f'{print_prefix} generating documentation from {doxyfile}:')
        os.system(f'doxygen {doxyfile}')


class AndroidBuildContext(BuildContext):
    """Build context for Android. This defines the logic for packaging all binaries into one AAR"""

    def __init__(self, conan: Conan, working_directory: str, target: str, version: str, build_directory: str,
                 profile: str, architectures: [Architecture],
                 configuration: BuildConfiguration, android_ndk: str, conan_cmake_toolchain_file: str,
                 android_project_dir: str, android_module_dir: str,
                 java_11_home: str, java_8_home: str):
        super().__init__(
            conan=conan,
            working_directory=working_directory,
            target=target,
            version=version,
            build_directory=build_directory,
            profile=profile,
            architectures=architectures,
            configuration=configuration,
            env=[f"CONAN_CMAKE_TOOLCHAIN_FILE={conan_cmake_toolchain_file}",
                 f"ANDROID_NDK={android_ndk}",
                 f"JAVA_HOME=\"{java_8_home}\""])
        self.java_11_home = java_11_home
        self.android_project_dir = android_project_dir
        self.android_module_dir = android_module_dir

    def install(self):
        for architecture in self.architectures:
            self.conan_install(architecture=architecture,
                               env=[f"ANDROID_ABI={architecture.value.android}"])

    def conan_create_all(self):
        for architecture in self.architectures:
            self.conan_create(architecture=architecture,
                              env=[f"ANDROID_ABI={architecture.value.android}"])

    def package(self):
        """copies all resources into the Android Studio project and builds it"""
        print(f'{print_prefix} packaging to AAR:')
        for architecture in self.architectures:
            print(
                f'{print_prefix} copy `lib{self.target}.so` for architecture {architecture.value.conan} to Android Studio Project')
            shutil.copy(src=f'{self.build_directory}/{architecture.value.conan}/lib/lib{self.target}.so',
                        dst=f'{self.android_module_dir}/src/main/jniLibs/{architecture.value.android}')
        print(f'{print_prefix} copy `{self.target}.jar` to Android Studio Project')
        shutil.copy(src=f'{self.build_directory}/{self.architectures[0].value.conan}/lib/{self.target}.jar',
                    dst=f'{self.android_module_dir}/libs')
        print(f'{print_prefix} build Android Studio Project')
        os.chdir(self.android_project_dir)
        os.putenv('JAVA_HOME', self.java_11_home)
        ret = os.system(f'./gradlew assemble{self.configuration.value}')
        os.chdir(self.working_directory)
        if ret != 0:
            print(f'{print_prefix} building Android Studio Project has failed', file=sys.stderr)
            exit(2)
        shutil.copy(src=f'{self.android_module_dir}/build/outputs/aar/{self.target}-{self.configuration.name}.aar',
                    dst=f'{self.build_directory}/{self.target}.aar')

    @staticmethod
    def render_doxygen_docs():
        """renders the doxygen documentation for Java"""
        BuildContext.render_doxygen_docs('Doxyfile-Java')


class DarwinBuildContext(BuildContext):
    """Build Context for iOS,macOS. This defines the logic for packaging all binaries into a single XCFramework"""

    def __init__(self, conan: Conan, working_directory: str, target: str, version: str, build_directory: str,
                 profile: str, architectures: list[Architecture],
                 configuration: BuildConfiguration, sdk: str):
        super().__init__(conan, working_directory, target, version, build_directory, profile, architectures,
                         configuration)
        self.sdk = sdk

    def install(self):
        for architecture in self.architectures:
            self.conan_install(architecture=architecture,
                               settings=[f'os.sdk={self.sdk}'])

    def conan_create_all(self):
        for architecture in self.architectures:
            self.conan_create(
                architecture=architecture,
                settings=[f'os.sdk={self.sdk}'])

    @property
    def target_folder(self):
        """determines the name of the folder in which the XCode build will output the binaries. The folder name
        differs depending on the target platform."""
        folder_name = self.configuration.value
        if self.sdk in ['iphoneos', 'iphonesimulator']:
            folder_name = f'{self.configuration.value}-{self.sdk}'
        return folder_name

    @property
    def combined_architecture(self):
        """determines the name of a target folder that contains a universal binary targeting multiple architectures.
        This is not the name used inside the XCFramework, it's just used for temporarily storing the generated
        universal binary."""
        return '_'.join(map(str, self.architectures))

    def build(self):
        """builds the binaries for each architecture and combines the resulting frameworks with lipo into a universal
        binary framework"""
        super().build()
        if len(self.architectures) > 1:
            lipo_dir = f"{self.build_directory}/{self.combined_architecture}"
            if os.path.exists(lipo_dir):
                shutil.rmtree(lipo_dir)
            os.mkdir(lipo_dir)
            shutil.copytree(
                src=f'{self.build_directory}/{self.architectures[0]}/lib/{self.target_folder}/{self.target}.framework',
                dst=f'{lipo_dir}/lib/{self.target_folder}/{self.target}.framework', symlinks=True)
            lipo_input: str = ''
            lipo_output: str = f'{lipo_dir}/lib/{self.target_folder}/{self.target}.framework/{self.target}'
            if self.sdk == 'macosx':
                lipo_output: str = f'{lipo_dir}/lib/{self.target_folder}/{self.target}.framework/Versions/A/{self.target}'
            for architecture in self.architectures:
                if self.sdk == 'macosx':
                    lipo_input += f'{self.build_directory}/{architecture}/lib/{self.target_folder}/{self.target}.framework/Versions/A/{self.target} '
                else:
                    lipo_input += f'{self.build_directory}/{architecture}/lib/{self.target_folder}/{self.target}.framework/{self.target} '
            os.system(
                f'lipo {lipo_input} -create -output {lipo_output}')

    @staticmethod
    def package(build_context_list: [BuildContext], target: str,
                build_directory: str):
        """combines the frameworks targeting different architectures into one big XCFramework for distribution."""
        print(f'{print_prefix} packaging to xcframework:')
        output_file = f'{build_directory}/{target}.xcframework'
        arguments = f'-output {output_file} '
        for build_context in build_context_list:
            if build_context.architectures is not None:
                arguments += f"-framework {build_context.build_directory}/{build_context.combined_architecture}/lib/{build_context.target_folder}/{target}.framework "
        if os.path.exists(output_file):
            shutil.rmtree(output_file)
        os.system(f'xcodebuild -create-xcframework {arguments}')

    @staticmethod
    def swiftpackage(swiftpackage_dir: str, target: str, build_directory: str):
        print(f'{print_prefix} creating swift package:')
        xcframework_dir = f'{build_directory}/{target}.xcframework'
        target_xcframework_dir = f'{swiftpackage_dir}/bin/{target}.xcframework'
        swiftpackage_target_dir = f'{build_directory}/{target}.swiftpackage'
        if os.path.exists(target_xcframework_dir):
            shutil.rmtree(target_xcframework_dir)
        if os.path.exists(swiftpackage_target_dir):
            shutil.rmtree(swiftpackage_target_dir)
        print(f'{print_prefix} copying xcframework to swiftpackage directory...')
        shutil.copytree(src=xcframework_dir,
                        dst=target_xcframework_dir,
                        symlinks=True)
        print(f'{print_prefix} copying swiftpackage directory with all contents to build directory...')
        shutil.copytree(src=swiftpackage_dir,
                        dst=swiftpackage_target_dir,
                        symlinks=True,
                        ignore=shutil.ignore_patterns(".gitignore"))

    @staticmethod
    def render_doxygen_docs():
        """renders the doxygen documentation for Objective-C"""
        BuildContext.render_doxygen_docs('Doxyfile-ObjC')


class WindowsBuildContext(BuildContext):
    """Build context for Windows (.NET 5.0). This defines the logic for packaging the dlls for multiple architectures
    into one NuGet package for distribution."""

    def __init__(self, conan: Conan, working_directory: str, target: str, version: str, build_directory: str,
                 profile: str, architectures: list[Architecture],
                 configuration: BuildConfiguration, nupkg_dir: str):
        super().__init__(conan, working_directory, target, version, build_directory, profile, architectures,
                         configuration)
        self.nupkg_dir = nupkg_dir

    def install(self):
        for architecture in self.architectures:
            self.conan_install(architecture=architecture)

    def conan_create_all(self):
        for architecture in self.architectures:
            self.conan_create(architecture=architecture)

    def package(self):
        """Copies all dlls into the NuGet template in `lib/platform/windows` and runs `nuget pack`. The resulting
        nupkg will be copied to the build output folder """
        print(f'{print_prefix} packaging to NuGet package:')
        nuspec = f'{self.target}.nuspec'
        shutil.copy(
            src=f'{self.build_directory}/{self.architectures[0].name}/lib/{self.configuration.value}/{self.target}.dll',
            dst=f'{self.nupkg_dir}/lib/net5.0/')
        for architecture in self.architectures:
            destination = f'{self.nupkg_dir}/runtimes/{architecture.value.windows}/lib/net5.0/'
            shutil.copy(src=f'{self.build_directory}/{architecture.name}/lib/{self.configuration.value}/{self.target}.dll',
                        dst=destination)
            shutil.copy(src=f'{self.build_directory}/{architecture.name}/lib/{self.configuration.value}/Ijwhost.dll',
                        dst=destination)
        self.configure_nuspec(f'{self.nupkg_dir}/{nuspec}')
        os.chdir(self.nupkg_dir)
        os.system(f'nuget pack {nuspec}')
        os.chdir(self.working_directory)
        shutil.copy(src=f'{self.nupkg_dir}/{self.target}.{self.version}.nupkg',
                    dst=f'{self.build_directory}/')

    def configure_nuspec(self, nuspec: str):
        """Writes the current version defined in the VERSION file into the nuspec template"""
        with open(f'{nuspec}.template', 'rt') as fin:
            with open(f'{nuspec}', "wt") as fout:
                for line in fin:
                    fout.write(line.replace('{version}', self.version))

    @staticmethod
    def render_doxygen_docs():
        """renders the doxygen documentation for C++/CLI"""
        BuildContext.render_doxygen_docs('Doxyfile-CppCli')


class DjinniBuild:

    def __init__(self, working_directory: str, target: str, version: str, android_profile: str,
                 macos_profile: str, ios_profile: str,
                 windows_profile: str, android_project_dir: str,
                 android_module_dir: str, nupkg_dir: str, swiftpackage_dir: str):
        """
        :param working_directory:   Absolute path to the root directory of the Djinni project.
        :param target:              Name of the target defined in CMake and name of the resulting binaries.
                                    Used to locate the binaries created by the build.
        :param version:             Version of the library. Will be used to set version metadata in the NuGet package.
        :param android_profile:     Absolute path to the conan profile that should be used to build for Android.
        :param macos_profile:       Absolute path to conan profile that should be used to build for macOS.
        :param ios_profile:         Absolute path to conan profile that should be used to build for iOS.
        :param windows_profile:     Absolute path to conan profile that should be used to build for Windows.
        :param android_project_dir: Absolute path to the Android project that is used to build the AAR.
        :param android_module_dir:  Absolute path to the Android project module that represents the Android Library.
                                    The Djinni jar will be copied to ./libs inside this directory.
                                    The Djinni native binaries will be copied to ./src/main/jniLibs/<architecture>
                                    inside this directory.
        :param nupkg_dir:           Absolute path to the folder containing the nuspec template + the NuGet package
                                    folder structure.
                                    The Djinni library binaries will be copied to ./runtimes/<architecture> inside this
                                    directory.
        :param swiftpackage_dir:    Absolute path to the folder that contains the Package.swift file used for the
                                    swift package.
        """
        self.working_directory = working_directory
        self.target: str = target
        self.version = version
        self.android_profile = android_profile
        self.macos_profile = macos_profile
        self.ios_profile = ios_profile
        self.windows_profile = windows_profile
        self.android_project_dir: str = android_project_dir
        self.android_module_dir: str = android_module_dir
        self.nupkg_dir = nupkg_dir
        self.swiftpackage_dir = swiftpackage_dir

    def main(self):
        """Main entrypoint of build.py. Parses the given CLI parameters & initializes the build contexts for the selected
        target platforms accordingly"""
        parser = argparse.ArgumentParser(description='Build & package library for different platforms')
        parser.add_argument('--configuration', dest='configuration', type=BuildConfiguration.from_string,
                            choices=list(BuildConfiguration), default=BuildConfiguration.release)
        parser.add_argument('--android', nargs='*', dest='android_architectures', type=Architecture.from_string,
                            choices=list(Architecture),
                            help="list of architectures that the library should be built for android")
        parser.add_argument('--aar', action='store_const', const=True, dest='package_aar',
                            help='wether to package the resulting binaries as AAR for Android')
        parser.add_argument('--macos', nargs='*', dest='macos_architectures', type=Architecture.from_string,
                            choices=list([Architecture.armv8, Architecture.x86_64]))
        parser.add_argument('--iphonesimulator', nargs='*', dest='iphonesimulator_architectures',
                            type=Architecture.from_string,
                            choices=list([Architecture.armv8, Architecture.x86_64]))
        parser.add_argument('--iphoneos', nargs='*', dest='iphoneos_architectures', type=Architecture.from_string,
                            choices=list([Architecture.armv8, Architecture.armv7]))
        parser.add_argument('--xcframework', action='store_const', const=True, dest='xcframework',
                            help='wether to package all macOS/iOS related binaries into an xcframework')
        parser.add_argument('--swiftpackage', action='store_const', const=True, dest='swiftpackage',
                            help='copy resulting xcframework into swiftpackage directory')
        parser.add_argument('--windows', nargs='*', dest='windows_architectures', type=Architecture.from_string,
                            choices=list(Architecture),
                            help='list of architectures to build for windows')
        parser.add_argument('--nuget', action='store_const', const=True, dest='nuget',
                            help='wether to package the resulting dlls as nuget for windows')
        parser.add_argument('--build-directory', dest='build_directory', type=str, default="build")
        parser.add_argument('--android-ndk', dest='android_ndk', type=str, help='directory of the NDK installation')
        parser.add_argument('--java-8-home', dest='java_8_home', type=str,
                            help='JAVA_HOME for a Java 1.8 installation. Required if building for Android')
        parser.add_argument('--java-11-home', dest='java_11_home', type=str,
                            help='JAVA_HOME for a Java Version > 11. Required if building for Android')
        parser.add_argument('--conan-create', action='store_const', const=True, dest='conan_create',
                            help='create the conan package for the given configuration')
        parser.add_argument('--render-docs', action='store_const', const=True, dest='render_docs',
                            help='render doxygen documentation for the languages of the selected target platforms')

        arguments = parser.parse_args()
        arguments.build_directory = os.path.abspath(arguments.build_directory)

        conan = Conan()
        if arguments.android_architectures:
            message_template = Template('Missing parameter: `$parameter` is required if building for Android!')
            missing_parameter: bool = False
            if not arguments.android_ndk:
                missing_parameter = True
                print(message_template.substitute(parameter='--android-ndk'), file=sys.stderr)
            if not arguments.java_8_home:
                missing_parameter = True
                print(message_template.substitute(parameter='--java-8-home'), file=sys.stderr)
            if not arguments.java_11_home and arguments.package_aar:
                missing_parameter = True
                print(message_template.substitute(parameter='--java-11-home'), file=sys.stderr)
            if missing_parameter:
                print()
                parser.print_help()
                exit(1)

            android = AndroidBuildContext(
                conan=conan,
                working_directory=self.working_directory,
                target=self.target,
                version=self.version,
                build_directory=f'{arguments.build_directory}/android',
                profile=self.android_profile,
                architectures=arguments.android_architectures,
                configuration=arguments.configuration,
                android_ndk=arguments.android_ndk,
                conan_cmake_toolchain_file=f'{os.path.abspath(os.path.dirname(__file__))}/cmake/toolchains/android_toolchain.cmake',
                android_module_dir=self.android_module_dir,
                android_project_dir=self.android_project_dir,
                java_8_home=arguments.java_8_home,
                java_11_home=arguments.java_11_home)
            android.install()
            android.build()
            if arguments.package_aar:
                android.package()
            if arguments.conan_create:
                android.conan_create_all()
            if arguments.render_docs:
                AndroidBuildContext.render_doxygen_docs()

        macos = DarwinBuildContext(
            conan=conan,
            working_directory=self.working_directory,
            target=self.target,
            version=self.version,
            build_directory=f'{arguments.build_directory}/macos',
            profile=self.macos_profile,
            architectures=arguments.macos_architectures,
            configuration=arguments.configuration,
            sdk='macosx')
        iphone = DarwinBuildContext(
            conan=conan,
            working_directory=self.working_directory,
            target=self.target,
            version=self.version,
            build_directory=f'{arguments.build_directory}/iphone',
            profile=self.ios_profile,
            architectures=arguments.iphoneos_architectures,
            configuration=arguments.configuration,
            sdk='iphoneos')
        iphonesimulator = DarwinBuildContext(
            conan=conan,
            working_directory=self.working_directory,
            target=self.target,
            version=self.version,
            build_directory=f'{arguments.build_directory}/iphonesimulator',
            profile=self.ios_profile,
            architectures=arguments.iphonesimulator_architectures,
            configuration=arguments.configuration,
            sdk='iphonesimulator')
        if arguments.macos_architectures is not None:
            macos.install()
            macos.build()
            if arguments.conan_create:
                macos.conan_create_all()
        if arguments.iphonesimulator_architectures is not None:
            iphonesimulator.install()
            iphonesimulator.build()
            if arguments.conan_create:
                iphonesimulator.conan_create_all()
        if arguments.iphoneos_architectures is not None:
            iphone.install()
            iphone.build()
            if arguments.conan_create:
                iphone.conan_create_all()

        if arguments.render_docs and (
                (arguments.macos_architectures is not None) or (
                arguments.iphonesimulator_architectures is not None) or (
                        arguments.iphoneos_architectures is not None)):
            DarwinBuildContext.render_doxygen_docs()

        if arguments.xcframework:
            DarwinBuildContext.package(build_context_list=[iphonesimulator, iphone, macos],
                                       target=self.target,
                                       build_directory=arguments.build_directory)

            if arguments.swiftpackage:
                DarwinBuildContext.swiftpackage(self.swiftpackage_dir,
                                                target=self.target,
                                                build_directory=arguments.build_directory)

        if arguments.windows_architectures:
            windows = WindowsBuildContext(
                conan=conan,
                working_directory=self.working_directory,
                target=self.target,
                version=self.version,
                build_directory=f'{arguments.build_directory}/windows',
                profile=self.windows_profile,
                architectures=arguments.windows_architectures,
                configuration=arguments.configuration,
                nupkg_dir=self.nupkg_dir)
            windows.install()
            windows.build()
            if arguments.nuget:
                windows.package()
            if arguments.conan_create:
                windows.conan_create_all()
            if arguments.render_docs:
                WindowsBuildContext.render_doxygen_docs()

        if arguments.render_docs:
            BuildContext.render_doxygen_docs('Doxyfile-Cpp')

