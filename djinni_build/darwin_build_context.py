from .build_context import BuildContext
from .argparse_enums import Architecture, BuildConfiguration
from .print_prefixed import print_prefixed
from conans.client.conan_api import Conan
from pathlib import Path


class DarwinBuildContext(BuildContext):
    """Build Context for iOS,macOS. This defines the logic for packaging all binaries into a single XCFramework"""

    def __init__(self,
                 conan: Conan,
                 working_directory: Path,
                 darwin_target: str,
                 darwin_target_dir: Path,
                 build_directory: Path,
                 host_profile: str | Path,
                 build_profile: str | Path,
                 architectures: list[Architecture],
                 configuration: BuildConfiguration,
                 sdk: str,
                 conan_user: str,
                 conan_channel: str):
        super().__init__(conan, working_directory, build_directory / sdk, host_profile, build_profile, architectures,
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
            self._lipo_combine(lipo_dir, self.darwin_target, self.darwin_target_dir)
            self._lipo_combine_dsym(lipo_dir, self.darwin_target, self.darwin_target_dir)

    def _lipo_combine(self, lipo_dir: Path, target: str, target_dir: Path):
        """combines multiple architectures into one multi-architecture framework."""
        BuildContext._copy_directory(
            src_dir=self.build_directory / self.architectures[0].value.conan / target_dir / self.target_folder / f'{target}.framework',
            target_dir=lipo_dir / target_dir / self.target_folder / f'{target}.framework')
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
        BuildContext._execute('lipo', [str(x) for x in lipo_input] + ['-create', f'-output {lipo_output}'])

    def _lipo_combine_dsym(self, lipo_dir: Path, target: str, target_dir: Path):
        """combines dSYM information for multiple architectures into one multi-architecture binary, if available"""
        dsym_src = self.build_directory / self.architectures[0].value.conan / target_dir / self.target_folder / f'{target}.framework.dSYM'
        if dsym_src.exists():
            print_prefixed(f'found debug symbols (dSYM). Combining with lipo...')
            BuildContext._copy_directory(
                src_dir=dsym_src,
                target_dir=lipo_dir / target_dir / self.target_folder / f'{target}.framework.dSYM'
            )
            lipo_input: list[Path] = []
            lipo_output: Path = lipo_dir / target_dir / self.target_folder / f'{target}.framework.dSYM' / 'Contents' / 'Resources' / 'DWARF' / target
            for architecture in self.architectures:
                lipo_input.append(
                    self.build_directory / architecture.name / target_dir / self.target_folder / f'{target}.framework.dSYM' / 'Contents' / 'Resources' / 'DWARF' / target)
            BuildContext._execute('lipo', [str(path) for path in lipo_input] + ['-create', f'-output {lipo_output}'])

    @staticmethod
    def package(build_context_list: [BuildContext], darwin_target: str,
                darwin_target_dir: Path, build_directory: Path):
        """combines the frameworks targeting different architectures into one big XCFramework for distribution."""
        DarwinBuildContext._create_xcframework(build_context_list, darwin_target, darwin_target_dir, build_directory)

    @staticmethod
    def _create_xcframework(build_context_list: [BuildContext], target: str, target_dir: Path, build_directory: Path):
        print_prefixed(f'packaging to xcframework:')
        output_dir: Path = build_directory / 'darwin' / 'package' / f'{target}.xcframework'
        arguments = ['-create-xcframework', f'-output {output_dir}']
        for build_context in build_context_list:
            if build_context.architectures is not None:
                framework_base_path = build_context.build_directory / build_context.combined_architecture / target_dir / build_context.target_folder
                framework_path = framework_base_path / f"{target}.framework"
                dsym_path = framework_base_path / f"{target}.framework.dSYM"
                arguments.append(f'-framework {framework_path}')
                if dsym_path.exists():
                    print_prefixed(f'found debug symbols (dSYM). Including them into the xcframework.')
                    arguments.append(f'-debug-symbols {dsym_path.resolve()}')
        BuildContext._clean(output_dir)
        BuildContext._execute('xcodebuild', arguments)

    @staticmethod
    def swiftpackage(swiftpackage_dir: Path, darwin_target: str,
                     build_directory: Path):
        print_prefixed('creating swift package:')

        swiftpackage_target_dir = build_directory / 'darwin' / 'swiftpackage'
        xcframework_src_dir = build_directory / 'darwin' / 'package' / f'{darwin_target}.xcframework'
        xcframework_target_dir = swiftpackage_target_dir / 'bin' / f'{darwin_target}.xcframework'

        BuildContext._copy_directory(swiftpackage_dir, swiftpackage_target_dir)
        BuildContext._copy_directory(xcframework_src_dir, xcframework_target_dir)
