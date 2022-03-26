from .build_context import BuildContext
from .argparse_enums import Architecture, BuildConfiguration
from .print_prefixed import print_prefixed
from conans.client.conan_api import Conan
import shutil
import os
import glob
from pathlib import Path


class WindowsBuildContext(BuildContext):
    """Build context for Windows (NET Core). This defines the logic for packaging the dlls for multiple architectures
    into one NuGet package for distribution."""

    def __init__(self,
                 conan: Conan,
                 working_directory: Path,
                 windows_target: str,
                 windows_target_dir: Path,
                 version: str,
                 build_directory: Path,
                 host_profile: str | Path,
                 build_profile: str | Path,
                 architectures: list[Architecture],
                 configuration: BuildConfiguration,
                 conan_user: str,
                 conan_channel: str,
                 nupkg_dir: Path,
                 nupkg_net_version: str,
                 nupkg_name: str):
        super().__init__(conan, working_directory, version, build_directory, host_profile, build_profile, architectures,
                         configuration, conan_user, conan_channel)
        self.nupkg_dir = nupkg_dir
        self.nupkg_net_version = nupkg_net_version
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
        print_prefixed('packaging to NuGet package:')
        nuspec = f'{self.nupkg_name}.nuspec'
        self._copy_target_to_nuget(self.architectures[0], self.windows_target, self.windows_target_dir,
                                   self.nupkg_dir/'lib'/self.nupkg_net_version)
        for architecture in self.architectures:
            ijwhost_dll = 'Ijwhost.dll'
            destination = self.nupkg_dir/'runtimes'/architecture.value.windows/'lib'/self.nupkg_net_version
            self._copy_target_to_nuget(architecture, self.windows_target, self.windows_target_dir, destination)
            shutil.copy(
                src=self.build_directory/architecture.name/self.windows_target_dir/self.configuration.value/ijwhost_dll,
                dst=destination/ijwhost_dll)
        self.configure_nuspec(self.nupkg_dir/nuspec)
        os.chdir(self.nupkg_dir)
        os.system(f'nuget pack {nuspec}')
        os.chdir(self.working_directory)
        nupkg_file = f'{self.nupkg_name}.{self.version}.nupkg'
        shutil.copy(src=self.nupkg_dir/nupkg_file,
                    dst=self.build_directory/nupkg_file)

    def _copy_target_to_nuget(self, architecture: Architecture, target: str, target_dir: Path, nuget_dir: Path):
        target_dll = f'{target}.dll'
        shutil.copy(
            src=self.build_directory/architecture.name/target_dir/self.configuration.value/target_dll,
            dst=nuget_dir/target_dll)

    def configure_nuspec(self, nuspec: Path):
        """Writes the current version defined in the VERSION file into the nuspec template"""
        with open(f'{nuspec}.template', 'rt') as fin:
            with open(nuspec, "wt") as fout:
                for line in fin:
                    fout.write(line.replace('{version}', self.version))

    @staticmethod
    def clean(windows_target: str, nuget_dir: Path, nupkg_net_version: str, nupkg_name: str):
        print_prefixed(f'Cleaning Windows build artifacts in {nuget_dir}')
        files = glob.glob(str(nuget_dir/f'{nupkg_name}.*.nupkg'))
        files.append(str(nuget_dir/'lib'/nupkg_net_version/'{windows_target}.dll'))
        files.append(str(nuget_dir/f'{nupkg_name}.nuspec'))

        for file in files:
            try:
                print_prefixed(f'  Removing {file}')
                os.remove(file)
            except OSError:
                pass

        for architecture in Architecture:
            ijwhost_dll = nuget_dir/'runtimes'/architecture.value.windows/'lib'/nupkg_net_version/'Ijwhost.dll'
            platform_dll = nuget_dir/'runtimes'/architecture.value.windows/'lib'/nupkg_net_version/f'{windows_target}.dll'
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
