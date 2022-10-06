from .argparse_enums import Architecture, BuildConfiguration, PackageType
from .android_build_context import AndroidBuildContext
from .darwin_build_context import DarwinBuildContext
from .windows_build_context import WindowsBuildContext
from .linux_build_context import LinuxBuildContext
from conans.client.conan_api import Conan
from pathlib import Path
import argparse


class DjinniBuild:

    def __init__(self,
                 darwin_target: str,
                 android_target: str,
                 android_module_name: str,
                 windows_target: str,
                 nupkg_name: str,
                 conan_user: str = '_',
                 conan_channel: str = '_',
                 default_build_dir: Path = Path('build'),
                 default_conan_build_profile: str | Path = 'default',
                 working_directory: Path = Path.cwd(),
                 darwin_target_dir: Path = Path('lib')/'platform'/'darwin',
                 android_target_dir: Path = Path('lib')/'platform'/'android',
                 windows_target_dir: Path = Path('lib')/'platform'/'windows',
                 android_profile: str | Path = Path.cwd()/'conan'/'profiles'/'android',
                 macos_profile: str | Path = Path.cwd()/'conan'/'profiles'/'macos',
                 ios_profile: str | Path = Path.cwd()/'conan'/'profiles'/'ios',
                 windows_profile: str | Path = Path.cwd()/'conan'/'profiles'/'windows',
                 linux_profile: str | Path = Path.cwd()/'conan'/'profiles'/'linux',
                 nupkg_dir: Path = Path('lib')/'platform'/'windows'/'package',
                 android_project_dir: Path = Path('lib')/'platform'/'android'/'package',
                 swiftpackage_dir: Path = Path('lib')/'platform'/'darwin'/'package'):
        """
        :param darwin_target:               Name of the Darwin specific CMake target
        :param android_target:              Name of the Android specific CMake target.
        :param android_module_name:         Name of the Android project module that represents the Android Library.
                                            The Djinni jar will be copied to ./libs inside this directory.
                                            The Djinni native binaries will be copied to ./src/main/jniLibs/<architecture>
                                            inside this directory.
        :param windows_target:              Name of the Windows specific CMake target
        :param nupkg_name:                  Name of the Nupkg nuspec template ("[nupkg_name].nuspec.template")
        :param conan_user:                  conan user for package creation
        :param conan_channel:               conan channel for package creation
        :param default_build_dir:           Relative path to the default build directory. The user can override the value with
                                            the --build-directory parameter
        :param default_conan_build_profile: The name of the default conan build profile (profile of the platform on
                                            which the compilation tools are being executed)
        :param working_directory:           Absolute path to the root directory of the Djinni project.

        :param darwin_target_dir:           Relative location of the Darwin target definition

        :param android_target_dir:          Relative location of the Darwin target definition

        :param windows_target_dir:          Relative location of the Windows target definition

        :param android_profile:             Absolute path to or name of the conan profile that should be used to build for Android.
        :param macos_profile:               Absolute path to or name of conan profile that should be used to build for macOS.
        :param ios_profile:                 Absolute path to or name of conan profile that should be used to build for iOS.
        :param windows_profile:             Absolute path to or name of conan profile that should be used to build for Windows.
        :param linux_profile:               Absolute path to or name of conan profile that should be used to build for Linux.
        :param nupkg_dir:                   Relative path to the folder containing the nuspec template + the NuGet package
                                            folder structure.
                                            The Djinni library binaries will be copied to ./runtimes/<architecture> inside this
                                            directory.
        :param android_project_dir:         Relative path to the Android project that is used to build the AAR.
        :param swiftpackage_dir:            Relative path to the folder that contains the Package.swift file used for the
                                            swift package.



        """
        self.working_directory = working_directory
        self.darwin_target = darwin_target
        self.darwin_target_dir = darwin_target_dir
        self.windows_target = windows_target
        self.windows_target_dir = windows_target_dir
        self.android_target = android_target
        self.android_target_dir = android_target_dir
        self.android_profile = android_profile
        self.macos_profile = macos_profile
        self.ios_profile = ios_profile
        self.windows_profile = windows_profile
        self.linux_profile = linux_profile
        self.android_project_dir = android_project_dir
        self.android_module_name = android_module_name
        self.nupkg_dir = nupkg_dir
        self.nupkg_name = nupkg_name
        self.swiftpackage_dir = swiftpackage_dir
        self.conan_user = conan_user
        self.conan_channel = conan_channel

        self.default_build_dir = default_build_dir
        self.default_conan_build_profile = default_conan_build_profile

    def main(self):
        """Main entrypoint. Parses the given CLI parameters & initializes the build contexts for the selected
        target platforms accordingly"""
        parser = argparse.ArgumentParser(description='Build & package library for different platforms')
        parser.add_argument('--configuration', dest='configuration', type=BuildConfiguration.from_string,
                            choices=list(BuildConfiguration), default=BuildConfiguration.release)
        parser.add_argument('--android', nargs='*', dest='android_architectures', type=Architecture.from_string,
                            choices=list(Architecture),
                            help="list of architectures that the library should be built for android")
        parser.add_argument('--macos', nargs='*', dest='macos_architectures', type=Architecture.from_string,
                            choices=list([Architecture.armv8, Architecture.x86_64]),
                            help='list of architectures to build for macOS')
        parser.add_argument('--iphonesimulator', nargs='*', dest='iphonesimulator_architectures',
                            type=Architecture.from_string,
                            choices=list([Architecture.armv8, Architecture.x86_64]),
                            help='list of architectures to build for the iOS Simulator')
        parser.add_argument('--iphoneos', nargs='*', dest='iphoneos_architectures', type=Architecture.from_string,
                            choices=list([Architecture.armv8, Architecture.armv7]),
                            help='list of architectures to build for iOS')
        parser.add_argument('--windows', nargs='*', dest='windows_architectures', type=Architecture.from_string,
                            choices=list(Architecture),
                            help='list of architectures to build for windows')
        parser.add_argument('--linux', nargs='*', dest='linux_architectures', type=Architecture.from_string,
                            choices=list(Architecture),
                            help='list of architectures to build for linux')
        parser.add_argument('--build-directory', dest='build_directory', type=Path, default=self.default_build_dir)
        parser.add_argument('--build-profile', dest='conan_build_profile', type=str,
                            default=self.default_conan_build_profile)
        parser.add_argument('--package', nargs='*', dest='package_types', type=PackageType.from_string,
                            choices=list(PackageType),
                            help='which packages to create. Packages that cannot be created for the selected target '
                                 'platforms will be ignored.')

        arguments = parser.parse_args()

        conan = Conan()

        if arguments.android_architectures:
            android = AndroidBuildContext(
                conan=conan,
                working_directory=self.working_directory,
                android_target=self.android_target,
                android_target_dir=self.android_target_dir,
                build_directory=arguments.build_directory/'android',
                host_profile=self.android_profile,
                build_profile=arguments.conan_build_profile,
                architectures=arguments.android_architectures,
                configuration=arguments.configuration,
                conan_user=self.conan_user,
                conan_channel=self.conan_channel,
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
            build_directory=arguments.build_directory/'darwin',
            host_profile=self.macos_profile,
            build_profile=arguments.conan_build_profile,
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
            build_directory=arguments.build_directory/'darwin',
            host_profile=self.ios_profile,
            build_profile=arguments.conan_build_profile,
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
            build_directory=arguments.build_directory/'darwin',
            host_profile=self.ios_profile,
            build_profile=arguments.conan_build_profile,
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

        if arguments.package_types and PackageType.xcframework in arguments.package_types and (
                        arguments.macos_architectures is not None or
                        arguments.iphonesimulator_architectures is not None or
                        arguments.iphoneos_architectures is not None):
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
                build_directory=arguments.build_directory/'windows',
                host_profile=self.windows_profile,
                build_profile=arguments.conan_build_profile,
                architectures=arguments.windows_architectures,
                configuration=arguments.configuration,
                conan_user=self.conan_user,
                conan_channel=self.conan_channel,
                nupkg_dir=self.nupkg_dir,
                nupkg_name=self.nupkg_name)
            windows.install()
            windows.build()
            if arguments.package_types and PackageType.nuget in arguments.package_types:
                windows.package()
            if arguments.package_types and PackageType.conan in arguments.package_types:
                windows.conan_create_all()

        if arguments.linux_architectures:
            linux = LinuxBuildContext(
                conan=conan,
                working_directory=self.working_directory,
                build_directory=arguments.build_directory/'linux',
                host_profile=self.linux_profile,
                build_profile=arguments.conan_build_profile,
                architectures=arguments.linux_architectures,
                configuration=arguments.configuration,
                conan_user=self.conan_user,
                conan_channel=self.conan_channel
            )
            linux.install()
            linux.build()
            if arguments.package_types and PackageType.conan in arguments.package_types:
                linux.conan_create_all()