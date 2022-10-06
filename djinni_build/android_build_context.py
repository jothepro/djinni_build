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
                 build_directory: Path,
                 host_profile: str | Path,
                 build_profile: str | Path,
                 architectures: list[Architecture],
                 configuration: BuildConfiguration,
                 conan_user: str,
                 conan_channel: str,
                 android_project_dir: Path,
                 android_module_name: str):
        super().__init__(conan, working_directory, build_directory, host_profile, build_profile, architectures,
                         configuration, conan_user, conan_channel)
        self.android_project_dir = android_project_dir
        self.android_project_target_dir = self.build_directory / 'package'
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
        BuildContext._copy_directory(self.android_project_dir, self.android_project_target_dir)
        for architecture in self.architectures:
            lib_name = f'lib{self.android_target}.so'
            BuildContext._copy_file(
                src=self.build_directory / architecture.name / self.android_target_dir / lib_name,
                dst=self.android_project_target_dir / self.android_module_name / 'src' / 'main' / 'jniLibs' / architecture.value.android / lib_name
            )
        print_prefixed(f'copy `{self.android_target}.jar` to Android Studio Project')
        jar_name = f'{self.android_target}.jar'
        BuildContext._copy_file(
            src=self.build_directory / self.architectures[0].name / self.android_target_dir / jar_name,
            dst=self.android_project_target_dir / self.android_module_name / 'libs' / jar_name
        )
        print_prefixed('build Android Studio Project')
        ret = BuildContext._execute('./gradlew', [f'assemble{self.configuration.value}'],
                                    working_dir=self.android_project_target_dir)
        if ret != 0:
            print_prefixed('building Android Studio Project has failed', file=sys.stderr)
            exit(2)
        BuildContext._copy_file(
            src=self.android_project_target_dir / self.android_module_name / 'build' / 'outputs' / 'aar' / f'{self.android_module_name}-{self.configuration.name}.aar',
            dst=self.android_project_target_dir / f'{self.android_module_name}.aar'
        )