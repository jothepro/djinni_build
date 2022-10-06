from .build_context import BuildContext
from .argparse_enums import Architecture, BuildConfiguration
from .print_prefixed import print_prefixed
from conans.client.conan_api import Conan
import shutil
from xml.dom import minidom
from pathlib import Path


class WindowsBuildContext(BuildContext):
    """Build context for Windows (NET Core). This defines the logic for packaging the dlls for multiple architectures
    into one NuGet package for distribution."""

    def __init__(self,
                 conan: Conan,
                 working_directory: Path,
                 windows_target: str,
                 windows_target_dir: Path,
                 build_directory: Path,
                 host_profile: str | Path,
                 build_profile: str | Path,
                 architectures: list[Architecture],
                 configuration: BuildConfiguration,
                 conan_user: str,
                 conan_channel: str,
                 nupkg_dir: Path,
                 nupkg_name: str):
        super().__init__(conan, working_directory, build_directory, host_profile, build_profile, architectures,
                         configuration, conan_user, conan_channel)
        self.nupkg_dir = nupkg_dir
        self.nupkg_name = nupkg_name
        self.windows_target = windows_target
        self.windows_target_dir = windows_target_dir
        self.nupkg_net_version = self._extract_net_version()
        self.nupkg_target_dir = self.build_directory / 'package'

    def install(self):
        for architecture in self.architectures:
            self.conan_install(architecture=architecture)

    def conan_create_all(self):
        for architecture in self.architectures:
            self.conan_create(architecture=architecture)

    def package(self):
        """Copies all dlls into the NuGet template in `lib/platform/windows` and runs `nuget pack`. The resulting
        nupkg will be copied to the build output folder """
        print_prefixed('packaging to NuGet package:')
        BuildContext._copy_directory(self.nupkg_dir, self.nupkg_target_dir)
        dll_filename = f'{self.windows_target}.dll'
        BuildContext._copy_file(
            src=self.build_directory / self.architectures[0].name / self.windows_target_dir / str(
                self.configuration.value) / dll_filename,
            dst=self.nupkg_target_dir / 'ref' / self.nupkg_net_version / dll_filename)

        pdb_found = False
        for architecture in self.architectures:
            destination = self.nupkg_target_dir / 'runtimes' / architecture.value.windows / 'lib' / self.nupkg_net_version
            shutil.copytree(
                src=self.build_directory / architecture.name / self.windows_target_dir / str(self.configuration.value),
                dst=destination)
            pdb_found = (destination / f'{self.windows_target}.pdb').exists()

        nuget_arguments = ['pack', f'{self.nupkg_name}.nuspec']
        if pdb_found:
            nuget_arguments.append('-Symbols')
        nuget_arguments.append(f'-Properties Configuration={self.configuration.value};version={self.version}')
        BuildContext._execute('nuget', nuget_arguments, working_dir=self.nupkg_target_dir)

    def _extract_net_version(self):
        """reads the required net version from the given nuspec file"""
        parser = minidom.parse(str(self.nupkg_dir / f'{self.nupkg_name}.nuspec'))
        group = parser.getElementsByTagName('dependencies')[0].getElementsByTagName('group')[0]
        return group.attributes['targetFramework'].value
