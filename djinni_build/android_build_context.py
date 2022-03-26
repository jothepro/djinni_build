from .build_context import BuildContext
from .argparse_enums import Architecture, BuildConfiguration
from .print_prefixed import print_prefixed
from conans.client.conan_api import Conan
import shutil
import os
import sys
from pathlib import Path


class AndroidBuildContext(BuildContext):
    """Build context for Android. This defines the logic for packaging all binaries into one AAR"""

    def __init__(self,
                 conan: Conan,
                 working_directory: Path,
                 android_target: str,
                 android_target_dir: Path,
                 version: str,
                 build_directory: Path,
                 host_profile: str | Path,
                 build_profile: str | Path,
                 architectures: list[Architecture],
                 configuration: BuildConfiguration,
                 conan_user: str,
                 conan_channel: str,
                 android_project_dir: Path,
                 android_module_name: str):
        super().__init__(conan, working_directory, version, build_directory, host_profile, build_profile, architectures,
                         configuration, conan_user, conan_channel)
        self.android_project_dir = android_project_dir
        self.android_module_name = android_module_name
        self.android_target = android_target
        self.android_target_dir = android_target_dir

    def install(self):
        for architecture in self.architectures:
            self.conan_install(architecture=architecture)

    def conan_create_all(self):
        for architecture in self.architectures:
            self.conan_create(architecture=architecture)

    def package(self):
        """copies all resources into the Android Studio project and builds it"""
        print_prefixed('packaging to AAR:')
        for architecture in self.architectures:
            self._lib_copy(self.android_target, self.android_target_dir, architecture)
        print_prefixed(f'copy `{self.android_target}.jar` to Android Studio Project')
        jar_name = f'{self.android_target}.jar'
        shutil.copy(
            src=self.build_directory/self.architectures[0].name/self.android_target_dir/jar_name,
            dst=self.android_project_dir/self.android_module_name/'libs'/jar_name)
        print_prefixed('build Android Studio Project')
        os.chdir(self.android_project_dir)
        ret = os.system(f'./gradlew assemble{self.configuration.value}')
        os.chdir(self.working_directory)
        if ret != 0:
            print_prefixed('building Android Studio Project has failed', file=sys.stderr)
            exit(2)
        shutil.copy(
            src=self.android_project_dir/ self.android_module_name/'build'/'outputs'/'aar'/f'{self.android_module_name}-{self.configuration.name}.aar',
            dst=self.build_directory/f'{self.android_module_name}.aar')

    def _lib_copy(self, target: str, target_dir: Path, architecture: Architecture):
        print_prefixed(f'copy `lib{target}.so` for architecture {architecture.value.android} to Android Studio Project')
        lib_name = f'lib{target}.so'
        shutil.copy(src=self.build_directory/architecture.name/target_dir/lib_name,
                    dst=self.android_project_dir/self.android_module_name/'src'/'main'/'jniLibs'/architecture.value.android/lib_name)

    @staticmethod
    def clean(android_target: str, android_project_dir: Path, android_module_name: str):
        print_prefixed(f'Cleaning Android build artifacts in {android_project_dir/android_module_name}')
        jar_file = android_project_dir/android_module_name/'libs'/f'{android_target}.jar'
        try:
            print_prefixed(f'  Removing {jar_file}')
            os.remove(jar_file)
        except OSError:
            pass
        for architecture in Architecture:
            shared_lib_file = android_project_dir/android_module_name/'src'/'main'/'jniLibs'/architecture.value.android/f'lib{android_target}.so'
            try:
                print_prefixed(f'  Removing {shared_lib_file}')
                os.remove(shared_lib_file)
            except OSError:
                pass
