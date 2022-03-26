from .build_context import BuildContext
from .argparse_enums import Architecture, BuildConfiguration
from .print_prefixed import print_prefixed
from conans.client.conan_api import Conan
from pathlib import Path
import shutil
import os


class DarwinBuildContext(BuildContext):
    """Build Context for iOS,macOS. This defines the logic for packaging all binaries into a single XCFramework"""

    def __init__(self,
                 conan: Conan,
                 working_directory: Path,
                 darwin_target: str,
                 darwin_target_dir: Path,
                 version: str,
                 build_directory: Path,
                 host_profile: str | Path,
                 build_profile: str | Path,
                 architectures: list[Architecture],
                 configuration: BuildConfiguration,
                 sdk: str,
                 conan_user: str,
                 conan_channel: str):
        super().__init__(conan, working_directory, version, build_directory, host_profile, build_profile, architectures,
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
            lipo_dir = self.build_directory / self.combined_architecture
            if lipo_dir.exists():
                shutil.rmtree(lipo_dir)
            lipo_dir.mkdir(parents=True)
            self._lipo_combine(lipo_dir, self.darwin_target, self.darwin_target_dir)

    def _lipo_combine(self, lipo_dir: Path, target: str, target_dir: Path):
        shutil.copytree(
            src=self.build_directory / self.architectures[0].value.conan / target_dir / self.target_folder / f'{target}.framework',
            dst=lipo_dir / target_dir / self.target_folder / f'{target}.framework', symlinks=True)
        lipo_input: list[Path] = []
        if self.sdk == 'macosx':
            lipo_output: Path = lipo_dir / target_dir / self.target_folder / f'{target}.framework' / 'Versions' / 'A' / target
        else:
            lipo_output: Path = lipo_dir / target_dir / self.target_folder / f'{target}.framework' / target
        for architecture in self.architectures:
            if self.sdk == 'macosx':
                lipo_input.append(self.build_directory / architecture.name / target_dir / self.target_folder / f'{target}.framework' / 'Versions' / 'A' / target)
            else:
                lipo_input.append(self.build_directory / architecture.name / target_dir / self.target_folder / f'{target}.framework' / target)
        os.system(f'lipo {" ".join(str(x) for x in lipo_input)} -create -output {lipo_output}')

    @staticmethod
    def package(build_context_list: [BuildContext], darwin_target: str,
                darwin_target_dir: Path, build_directory: Path):
        """combines the frameworks targeting different architectures into one big XCFramework for distribution."""
        DarwinBuildContext._create_xcframework(build_context_list, darwin_target, darwin_target_dir, build_directory)

    @staticmethod
    def _create_xcframework(build_context_list: [BuildContext], target: str, target_dir: Path, build_directory: Path):
        print_prefixed(f'packaging to xcframework:')
        output_file: Path = build_directory / f'{target}.xcframework'
        arguments = f'-output {output_file} '
        for build_context in build_context_list:
            if build_context.architectures is not None:
                arguments += f"-framework {build_context.build_directory / build_context.combined_architecture / target_dir / build_context.target_folder / target}.framework "
        if output_file.exists():
            shutil.rmtree(output_file)
        os.system(f'xcodebuild -create-xcframework {arguments}')

    @staticmethod
    def swiftpackage(swiftpackage_dir: Path, darwin_target: str,
                     build_directory: Path):
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
    def _copy_to_swiftpackage(build_directory: Path, target: str, swiftpackage_dir: Path):
        xcframework_dir = build_directory / f'{target}.xcframework'
        target_xcframework_dir = swiftpackage_dir / 'bin' / f'{target}.xcframework'

        if target_xcframework_dir.exists():
            shutil.rmtree(target_xcframework_dir)

        print_prefixed('copying xcframework to swiftpackage directory...')
        shutil.copytree(src=xcframework_dir,
                        dst=target_xcframework_dir,
                        symlinks=True)

    @staticmethod
    def clean(darwin_target: str, swiftpackage_dir: Path):
        print_prefixed(f'Cleaning Darwin build artifacts in {swiftpackage_dir}')
        xcframework_dir = swiftpackage_dir / 'bin' / f'{darwin_target}.xcframework'
        try:
            print_prefixed(f'  Removing {xcframework_dir}')
            shutil.rmtree(xcframework_dir)
        except OSError:
            pass
