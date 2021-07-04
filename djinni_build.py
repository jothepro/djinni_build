#!/usr/bin/env python3

import argparse
import os
import glob
import sys
from enum import Enum
from collections import namedtuple
from conans.client.conan_api import Conan
from string import Template
import shutil

print_prefix = "[djinni-build.py]"

def print_prefixed(message: str):
    print(f'{print_prefix} {message}')

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

class PackageType(ArgparseEnum):
    xcframework = 'XCFramework'
    swiftpackage = 'Swift Package'
    conan = 'Conan'
    aar = 'Android Archive'
    nuget = 'NuGet'


class BuildContext:
    """Base class for all build contexts. Contains common code that is shared between builds for different
    languages/platforms """

    def __init__(self, conan: Conan, working_directory: str, version: str,
                 build_directory: str, profile: str, architectures: [Architecture],
                 configuration: BuildConfiguration, conan_user: str, conan_channel: str,
                 env: list[str] = [], settings: list[str] = []):
        self.conan = conan
        self.working_directory = working_directory
        self.version = version
        self.profile = profile
        self.build_directory = build_directory
        self.architectures = architectures
        self.configuration = configuration
        self.conan_user = conan_user
        self.conan_channel = conan_channel
        self.env = ['CONAN_RUN_TESTS=False'] + env
        self.settings = [f'build_type={self.configuration.value}'] + settings

    def build(self):
        """builds all selected architectures"""
        for architecture in self.architectures:
            print_prefixed(f'building for architecture {architecture.name}:')
            self.conan.build(conanfile_path=self.working_directory,
                             build_folder=f"{self.build_directory}/{architecture.value.conan}")

    def conan_install(self, architecture: Architecture, settings: list[str] = [],
                      env: list[str] = []):
        """installs all conan dependencies defined in conanfile.py"""
        print_prefixed(f'installing dependencies for architecture {architecture.name}:')
        all_settings = settings + self.settings + [f"arch={architecture.value.conan}"]
        all_env = env + self.env
        self.conan.install(install_folder=f"{self.build_directory}/{architecture.value.conan}",
                           profile_names=[self.profile], build=["missing"],
                           settings=all_settings,
                           env=all_env)

    def conan_create(self, architecture: Architecture, settings: list[str] = [],
                     env: list[str] = []):
        """creates the conan package for the current configuration"""
        print_prefixed(f'creating conan package for architecture {architecture.name}:')
        all_settings = settings + self.settings + [f"arch={architecture.value.conan}"]
        all_env = env + self.env
        self.conan.create(profile_names=[self.profile],
                          conanfile_path=self.working_directory,
                          settings=all_settings,
                          user=self.conan_user,
                          channel=self.conan_channel,
                          env=all_env)


class AndroidBuildContext(BuildContext):
    """Build context for Android. This defines the logic for packaging all binaries into one AAR"""

    def __init__(self, conan: Conan, working_directory: str, android_target: str,
                 android_target_dir: str, version: str, build_directory: str, profile: str, architectures: [Architecture],
                 configuration: BuildConfiguration, conan_user: str, conan_channel: str,
                 android_ndk: str, conan_cmake_toolchain_file: str,
                 android_project_dir: str, android_module_name: str):
        super().__init__(
            conan=conan,
            working_directory=working_directory,
            version=version,
            build_directory=build_directory,
            profile=profile,
            architectures=architectures,
            configuration=configuration,
            conan_user=conan_user,
            conan_channel=conan_channel,
            env=[f"CONAN_CMAKE_TOOLCHAIN_FILE={conan_cmake_toolchain_file}",
                 f"ANDROID_NDK={android_ndk}"])
        self.android_project_dir = android_project_dir
        self.android_module_name = android_module_name
        self.android_target = android_target
        self.android_target_dir = android_target_dir

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
            self._lib_copy(self.android_target, self.android_target_dir, architecture)
        print(f'{print_prefix} copy `{self.android_target}.jar` to Android Studio Project')
        shutil.copy(src=f'{self.build_directory}/{self.architectures[0].value.conan}/{self.android_target_dir}/{self.android_target}.jar',
                    dst=f'{self.android_project_dir}/{self.android_module_name}/libs')
        print(f'{print_prefix} build Android Studio Project')
        os.chdir(self.android_project_dir)
        ret = os.system(f'./gradlew assemble{self.configuration.value}')
        os.chdir(self.working_directory)
        if ret != 0:
            print(f'{print_prefix} building Android Studio Project has failed', file=sys.stderr)
            exit(2)
        shutil.copy(src=f'{self.android_project_dir}/{self.android_module_name}/build/outputs/aar/{self.android_module_name}-{self.configuration.name}.aar',
                    dst=f'{self.build_directory}/{self.android_module_name}.aar')

    def _lib_copy(self, target: str, target_dir: str, architecture: Architecture):
        print_prefixed(f'copy `lib{target}.so` for architecture {architecture.value.conan} to Android Studio Project')
        shutil.copy(src=f'{self.build_directory}/{architecture.value.conan}/{target_dir}/lib{target}.so',
                    dst=f'{self.android_project_dir}/{self.android_module_name}/src/main/jniLibs/{architecture.value.android}')


    @staticmethod
    def clean(android_target: str, android_project_dir: str, android_module_name: str):
        print_prefixed(f'Cleaning Android build artifacts in {android_project_dir}/{android_module_name}')
        jar_file = f'{android_project_dir}/{android_module_name}/libs/{android_target}.jar'
        try:
            print_prefixed(f'  Removing {jar_file}')
            os.remove(jar_file)
        except OSError:
            pass
        for architecture in Architecture:
            shared_lib_file = f'{android_project_dir}/{android_module_name}/src/main/jniLibs/{architecture.value.android}/lib{android_target}.so'
            try:
                print_prefixed(f'  Removing {shared_lib_file}')
                os.remove(shared_lib_file)
            except OSError:
                pass


class DarwinBuildContext(BuildContext):
    """Build Context for iOS,macOS. This defines the logic for packaging all binaries into a single XCFramework"""

    def __init__(self, conan: Conan, working_directory: str, darwin_target: str,
                 darwin_target_dir: str, version: str, build_directory: str, profile: str,
                 architectures: list[Architecture], configuration: BuildConfiguration, sdk: str,
                 conan_user: str, conan_channel: str):
        super().__init__(conan, working_directory, version, build_directory, profile, architectures,
                         configuration, conan_user, conan_channel)
        self.sdk = sdk
        self.darwin_target = darwin_target
        self.darwin_target_dir = darwin_target_dir

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
            self._lipo_combine(lipo_dir, self.darwin_target, self.darwin_target_dir)

    def _lipo_combine(self, lipo_dir: str, target: str, target_dir: str):
        shutil.copytree(
            src=f'{self.build_directory}/{self.architectures[0]}/{target_dir}/{self.target_folder}/{target}.framework',
            dst=f'{lipo_dir}/{target_dir}/{self.target_folder}/{target}.framework', symlinks=True)
        lipo_input: str = ''
        lipo_output: str = f'{lipo_dir}/{target_dir}/{self.target_folder}/{target}.framework/{target}'
        if self.sdk == 'macosx':
            lipo_output: str = f'{lipo_dir}/{target_dir}/{self.target_folder}/{target}.framework/Versions/A/{target}'
        for architecture in self.architectures:
            if self.sdk == 'macosx':
                lipo_input += f'{self.build_directory}/{architecture}/{target_dir}/{self.target_folder}/{target}.framework/Versions/A/{target} '
            else:
                lipo_input += f'{self.build_directory}/{architecture}/{target_dir}/{self.target_folder}/{target}.framework/{target} '
        os.system(
            f'lipo {lipo_input} -create -output {lipo_output}')

    @staticmethod
    def package(build_context_list: [BuildContext], darwin_target: str,
                darwin_target_dir: str, build_directory: str):
        """combines the frameworks targeting different architectures into one big XCFramework for distribution."""
        DarwinBuildContext._create_xcframework(build_context_list, darwin_target, darwin_target_dir, build_directory)


    @staticmethod
    def _create_xcframework(build_context_list: [BuildContext], target: str, target_dir: str, build_directory: str):
        print_prefixed(f'packaging to xcframework:')
        output_file = f'{build_directory}/{target}.xcframework'
        arguments = f'-output {output_file} '
        for build_context in build_context_list:
            if build_context.architectures is not None:
                arguments += f"-framework {build_context.build_directory}/{build_context.combined_architecture}/{target_dir}/{build_context.target_folder}/{target}.framework "
        if os.path.exists(output_file):
            shutil.rmtree(output_file)
        os.system(f'xcodebuild -create-xcframework {arguments}')

    @staticmethod
    def swiftpackage(swiftpackage_dir: str, darwin_target: str,
                     build_directory: str):
        print_prefixed('creating swift package:')
        DarwinBuildContext._copy_to_swiftpackage(build_directory, darwin_target, swiftpackage_dir)

        print_prefixed('copying swiftpackage directory with all contents to build directory...')
        swiftpackage_target_dir = f'{build_directory}/swiftpackage'
        if os.path.exists(swiftpackage_target_dir):
            shutil.rmtree(swiftpackage_target_dir)
        shutil.copytree(src=swiftpackage_dir,
                        dst=swiftpackage_target_dir,
                        symlinks=True,
                        ignore=shutil.ignore_patterns(".gitignore"))

    @staticmethod
    def _copy_to_swiftpackage(build_directory: str, target: str, swiftpackage_dir: str):
        xcframework_dir = f'{build_directory}/{target}.xcframework'
        target_xcframework_dir = f'{swiftpackage_dir}/bin/{target}.xcframework'

        if os.path.exists(target_xcframework_dir):
            shutil.rmtree(target_xcframework_dir)

        print(f'{print_prefix} copying xcframework to swiftpackage directory...')
        shutil.copytree(src=xcframework_dir,
                        dst=target_xcframework_dir,
                        symlinks=True)

    @staticmethod
    def clean(darwin_target: str, swiftpackage_dir: str):
        print_prefixed(f'Cleaning Darwin build artifacts in {swiftpackage_dir}')
        xcframework_dir = f'{swiftpackage_dir}/bin/{darwin_target}.xcframework'
        try:
            print_prefixed(f'  Removing {xcframework_dir}')
            shutil.rmtree(xcframework_dir)
        except OSError:
            pass


class WindowsBuildContext(BuildContext):
    """Build context for Windows (.NET 5.0). This defines the logic for packaging the dlls for multiple architectures
    into one NuGet package for distribution."""

    def __init__(self, conan: Conan, working_directory: str, windows_target: str,
                 windows_target_dir: str, version: str, build_directory: str, profile: str,
                 architectures: list[Architecture], configuration: BuildConfiguration,
                 conan_user: str, conan_channel: str, nupkg_dir: str, nupkg_name: str):
        super().__init__(conan, working_directory, version, build_directory, profile, architectures,
                         configuration, conan_user, conan_channel)
        self.nupkg_dir = nupkg_dir
        self.nupkg_name = nupkg_name
        self.windows_target = windows_target
        self.windows_target_dir = windows_target_dir

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
        nuspec = f'{self.nupkg_name}.nuspec'
        self._copy_target_to_nuget(self.architectures[0], self.windows_target, self.windows_target_dir, f'{self.nupkg_dir}/lib/net5.0/')
        for architecture in self.architectures:
            destination = f'{self.nupkg_dir}/runtimes/{architecture.value.windows}/lib/net5.0/'
            self._copy_target_to_nuget(architecture, self.windows_target, self.windows_target_dir, destination)
            shutil.copy(src=f'{self.build_directory}/{architecture.name}/{self.windows_target_dir}/{self.configuration.value}/Ijwhost.dll',
                        dst=destination)
        self.configure_nuspec(f'{self.nupkg_dir}/{nuspec}')
        os.chdir(self.nupkg_dir)
        os.system(f'nuget pack {nuspec}')
        os.chdir(self.working_directory)
        shutil.copy(src=f'{self.nupkg_dir}/{self.nupkg_name}.{self.version}.nupkg',
                    dst=f'{self.build_directory}/')

    def _copy_target_to_nuget(self, architecture: Architecture, target: str, target_dir: str, nuget_dir: str):
        shutil.copy(
            src=f'{self.build_directory}/{architecture.name}/{target_dir}/{self.configuration.value}/{target}.dll',
            dst=f'{nuget_dir}')

    def configure_nuspec(self, nuspec: str):
        """Writes the current version defined in the VERSION file into the nuspec template"""
        with open(f'{nuspec}.template', 'rt') as fin:
            with open(f'{nuspec}', "wt") as fout:
                for line in fin:
                    fout.write(line.replace('{version}', self.version))

    @staticmethod
    def clean(windows_target: str, nuget_dir: str, nupkg_name: str):
        print_prefixed(f'Cleaning Windows build artifacts in {nuget_dir}')
        files = glob.glob(f'{nuget_dir}/{nupkg_name}.*.nupkg')
        files.append(f'{nuget_dir}/lib/net5.0/{windows_target}.dll')
        files.append(f'{nuget_dir}/{nupkg_name}.nuspec')

        for file in files:
            try:
                print_prefixed(f'  Removing {file}')
                os.remove(file)
            except OSError:
                pass

        for architecture in Architecture:
            ijwhost_dll = f'{nuget_dir}/runtimes/{architecture.value.windows}/lib/net5.0/Ijwhost.dll'
            platform_dll = f'{nuget_dir}/runtimes/{architecture.value.windows}/lib/net5.0/{windows_target}.dll'
            try:
                print_prefixed(f'  Removing {ijwhost_dll}')
                os.remove(ijwhost_dll)
            except OSError:
                pass
            try:
                print_prefixed(f'  Removing {platform_dll}')
                os.remove(platform_dll)
            except OSError:
                pass

class LinuxBuildContext(BuildContext):
    def install(self):
        for architecture in self.architectures:
            self.conan_install(architecture=architecture)

    def conan_create_all(self):
        for architecture in self.architectures:
            self.conan_create(architecture=architecture)


class DjinniBuild:

    def __init__(self, working_directory: str, darwin_target: str, darwin_target_dir: str,
                 android_target: str, android_target_dir: str, windows_target: str, windows_target_dir: str,
                 version: str, android_profile: str, macos_profile: str, ios_profile: str,
                 windows_profile: str, linux_profile: str, android_project_dir: str,
                 android_module_name: str, nupkg_dir: str, nupkg_name: str, swiftpackage_dir: str, conan_user: str, conan_channel: str):
        """
        :param working_directory:   Absolute path to the root directory of the Djinni project.
        :param darwin_target:       Name of the Darwin specific CMake target
        :param darwin_target_dir:   Relative location of the Darwin target definition
        :param android_target:      Name of the Android specific CMake target.
        :param android_target_dir:  Relative location of the Darwin target definition
        :param windows_target:      Name of the Windows specific CMake target
        :param windows_target_dir:  Relative location of the Windows target definition
        :param version:             Version of the library. Will be used to set version metadata in the NuGet package.
        :param android_profile:     Relative path to the conan profile that should be used to build for Android.
        :param macos_profile:       Relative path to conan profile that should be used to build for macOS.
        :param ios_profile:         Relative path to conan profile that should be used to build for iOS.
        :param windows_profile:     Relative path to conan profile that should be used to build for Windows.
        :param android_project_dir: Relative path to the Android project that is used to build the AAR.
        :param android_module_dir:  Relative path to the Android project module that represents the Android Library.
                                    The Djinni jar will be copied to ./libs inside this directory.
                                    The Djinni native binaries will be copied to ./src/main/jniLibs/<architecture>
                                    inside this directory.
        :param nupkg_dir:           Relative path to the folder containing the nuspec template + the NuGet package
                                    folder structure.
                                    The Djinni library binaries will be copied to ./runtimes/<architecture> inside this
                                    directory.
        :param swiftpackage_dir:    Absolute path to the folder that contains the Package.swift file used for the
                                    swift package.
        :param conan_user:          conan user for package creation
        :param conan_channel:       conan channel for package creation
        """
        self.working_directory = working_directory
        self.darwin_target: str = darwin_target
        self.darwin_target_dir: str = darwin_target_dir
        self.windows_target: str = windows_target
        self.windows_target_dir: str = windows_target_dir
        self.android_target: str = android_target
        self.android_target_dir: str = android_target_dir
        self.version = version
        self.android_profile = f'{self.working_directory}/{android_profile}'
        self.macos_profile = f'{self.working_directory}/{macos_profile}'
        self.ios_profile = f'{self.working_directory}/{ios_profile}'
        self.windows_profile = f'{self.working_directory}/{windows_profile}'
        self.linux_profile = f'{self.working_directory}/{linux_profile}'
        self.android_project_dir: str = f'{self.working_directory}/{android_project_dir}'
        self.android_module_name: str = android_module_name
        self.nupkg_dir = f'{self.working_directory}/{nupkg_dir}'
        self.nupkg_name = nupkg_name
        self.swiftpackage_dir = f'{self.working_directory}/{swiftpackage_dir}'
        self.conan_user = conan_user
        self.conan_channel = conan_channel

    def main(self):
        """Main entrypoint of build.py. Parses the given CLI parameters & initializes the build contexts for the selected
        target platforms accordingly"""
        parser = argparse.ArgumentParser(description='Build & package library for different platforms')
        parser.add_argument('--configuration', dest='configuration', type=BuildConfiguration.from_string,
                            choices=list(BuildConfiguration), default=BuildConfiguration.release)
        parser.add_argument('--android', nargs='*', dest='android_architectures', type=Architecture.from_string,
                            choices=list(Architecture),
                            help="list of architectures that the library should be built for android")
        parser.add_argument('--macos', nargs='*', dest='macos_architectures', type=Architecture.from_string,
                            choices=list([Architecture.armv8, Architecture.x86_64]))
        parser.add_argument('--iphonesimulator', nargs='*', dest='iphonesimulator_architectures',
                            type=Architecture.from_string,
                            choices=list([Architecture.armv8, Architecture.x86_64]))
        parser.add_argument('--iphoneos', nargs='*', dest='iphoneos_architectures', type=Architecture.from_string,
                            choices=list([Architecture.armv8, Architecture.armv7]))
        parser.add_argument('--windows', nargs='*', dest='windows_architectures', type=Architecture.from_string,
                            choices=list(Architecture),
                            help='list of architectures to build for windows')
        parser.add_argument('--linux', nargs='*', dest='linux_architectures', type=Architecture.from_string,
                            choices=list(Architecture),
                            help='list of architectures to build for linux')
        parser.add_argument('--build-directory', dest='build_directory', type=str, default="build")
        parser.add_argument('--package', nargs='*', dest='package_types', type=PackageType.from_string,
                            choices=list(PackageType),
                            help='which packages to create. Packages that cannot be created for the selected target '
                                 'architectures will be ignored.')
        parser.add_argument('--clean', action='store_const', const=True, dest='cleanup',
                            help='clean all build artifacts outside of the build folder, that this script may have created')

        arguments = parser.parse_args()
        arguments.build_directory = os.path.abspath(arguments.build_directory)

        if(arguments.cleanup):
            self.clean()

        conan = Conan()

        if arguments.android_architectures:
            message_template = Template('Missing parameter: `$parameter` is required if building for Android!')
            missing_parameter: bool = False

            android_ndk = ''
            try:
                android_ndk = os.environ['ANDROID_NDK_HOME']
            except KeyError:
                print('Missing required environment variable ANDROID_NDK_HOME', file=sys.stderr)
                print()
                parser.print_help()
                exit(1)

            android = AndroidBuildContext(
                conan=conan,
                working_directory=self.working_directory,
                android_target=self.android_target,
                android_target_dir=self.android_target_dir,
                version=self.version,
                build_directory=f'{arguments.build_directory}/android',
                profile=self.android_profile,
                architectures=arguments.android_architectures,
                configuration=arguments.configuration,
                conan_user=self.conan_user,
                conan_channel=self.conan_channel,
                android_ndk=android_ndk,
                conan_cmake_toolchain_file=f'{os.path.abspath(os.path.dirname(__file__))}/cmake/toolchains/android_toolchain.cmake',
                android_module_name=self.android_module_name,
                android_project_dir=self.android_project_dir)
            android.install()
            android.build()
            if arguments.package_types and PackageType.aar in arguments.package_types:
                android.package()
            if arguments.package_types and PackageType.conan in arguments.package_types:
                android.conan_create_all()

        macos = DarwinBuildContext(
            conan=conan,
            working_directory=self.working_directory,
            darwin_target=self.darwin_target,
            darwin_target_dir=self.darwin_target_dir,
            version=self.version,
            build_directory=f'{arguments.build_directory}/macos',
            profile=self.macos_profile,
            architectures=arguments.macos_architectures,
            configuration=arguments.configuration,
            conan_user=self.conan_user,
            conan_channel=self.conan_channel,
            sdk='macosx')
        iphone = DarwinBuildContext(
            conan=conan,
            working_directory=self.working_directory,
            darwin_target=self.darwin_target,
            darwin_target_dir=self.darwin_target_dir,
            version=self.version,
            build_directory=f'{arguments.build_directory}/iphone',
            profile=self.ios_profile,
            architectures=arguments.iphoneos_architectures,
            configuration=arguments.configuration,
            conan_user=self.conan_user,
            conan_channel=self.conan_channel,
            sdk='iphoneos')
        iphonesimulator = DarwinBuildContext(
            conan=conan,
            working_directory=self.working_directory,
            darwin_target=self.darwin_target,
            darwin_target_dir=self.darwin_target_dir,
            version=self.version,
            build_directory=f'{arguments.build_directory}/iphonesimulator',
            profile=self.ios_profile,
            architectures=arguments.iphonesimulator_architectures,
            configuration=arguments.configuration,
            conan_user=self.conan_user,
            conan_channel=self.conan_channel,
            sdk='iphonesimulator')
        if arguments.macos_architectures is not None:
            macos.install()
            macos.build()
            if arguments.package_types and PackageType.conan in arguments.package_types:
                macos.conan_create_all()
        if arguments.iphonesimulator_architectures is not None:
            iphonesimulator.install()
            iphonesimulator.build()
            if arguments.package_types and PackageType.conan in arguments.package_types:
                iphonesimulator.conan_create_all()
        if arguments.iphoneos_architectures is not None:
            iphone.install()
            iphone.build()
            if arguments.package_types and PackageType.conan in arguments.package_types:
                iphone.conan_create_all()

        if arguments.package_types and PackageType.xcframework in arguments.package_types:
            DarwinBuildContext.package(build_context_list=[iphonesimulator, iphone, macos],
                                       darwin_target=self.darwin_target,
                                       darwin_target_dir=self.darwin_target_dir,
                                       build_directory=arguments.build_directory)

            if arguments.package_types and PackageType.swiftpackage in arguments.package_types:
                DarwinBuildContext.swiftpackage(self.swiftpackage_dir,
                                                darwin_target=self.darwin_target,
                                                build_directory=arguments.build_directory)

        if arguments.windows_architectures:
            windows = WindowsBuildContext(
                conan=conan,
                working_directory=self.working_directory,
                windows_target=self.windows_target,
                windows_target_dir=self.windows_target_dir,
                version=self.version,
                build_directory=f'{arguments.build_directory}/windows',
                profile=self.windows_profile,
                architectures=arguments.windows_architectures,
                configuration=arguments.configuration,
                conan_user=self.conan_user,
                conan_channel=self.conan_channel,
                nupkg_dir=self.nupkg_dir,
                nupkg_name=self.nupkg_name)
            windows.install()
            windows.build()
            if PackageType.nuget in arguments.package_types:
                windows.package()
            if PackageType.conan in arguments.package_types:
                windows.conan_create_all()

        if arguments.linux_architectures:
            linux = LinuxBuildContext(
                conan=conan,
                working_directory=self.working_directory,
                version=self.version,
                build_directory=f'{arguments.build_directory}/linux',
                profile=self.linux_profile,
                architectures=arguments.linux_architectures,
                configuration=arguments.configuration,
                conan_user=self.conan_user,
                conan_channel=self.conan_channel
            )
            linux.install()
            linux.build()
            if PackageType.conan in arguments.package_types:
                linux.conan_create_all()

    def clean(self):
        AndroidBuildContext.clean(self.android_target, self.android_project_dir, self.android_module_name)
        WindowsBuildContext.clean(self.windows_target, self.nupkg_dir, self.nupkg_name)
        DarwinBuildContext.clean(self.darwin_target, self.swiftpackage_dir)
