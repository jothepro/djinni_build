from .argparse_enums import Architecture, BuildConfiguration
from conans.client.conan_api import Conan, ProfileData
from .print_prefixed import print_prefixed
from pathlib import Path
import shutil
import os

class BuildContext:
    """Base class for all build contexts. Contains common code that is shared between builds for different
    languages/platforms """

    def __init__(self, conan: Conan,
                 working_directory: Path,
                 build_directory: Path,
                 host_profile: str | Path,
                 build_profile: str | Path,
                 architectures: list[Architecture],
                 configuration: BuildConfiguration,
                 conan_user: str,
                 conan_channel: str,
                 env: list[str] = [],
                 settings: list[str] = []):
        self.conan = conan
        self.working_directory = working_directory
        self.host_profile = host_profile
        self.build_profile = ProfileData(profiles=[str(build_profile)], settings=[], options=[], env=[], conf=[])
        self.build_directory = build_directory
        self.packaging_directory = build_directory / 'package'
        self.architectures = architectures
        self.configuration = configuration
        self.conan_user = conan_user
        self.conan_channel = conan_channel
        self.env = ['CONAN_RUN_TESTS=False'] + env
        self.settings = [f'build_type={self.configuration.value}'] + settings
        self.version = self.conan.inspect(path=str(self.working_directory), attributes=['version'])['version']

    def build(self):
        """builds all selected architectures"""
        for architecture in self.architectures:
            print_prefixed(f'building for architecture {architecture.name}:')
            self.conan.build(conanfile_path=str(self.working_directory),
                             build_folder=str(self.build_directory / architecture.name))

    def conan_install(self, architecture: Architecture, settings: list[str] = [],
                      env: list[str] = []):
        """installs all conan dependencies defined in conanfile.py"""
        print_prefixed(f'installing dependencies for architecture {architecture.name}:')
        all_settings = settings + self.settings + [f"arch={architecture.value.conan}"]
        all_env = env + self.env
        self.conan.install(install_folder=str(self.build_directory / architecture.name),
                           profile_names=[str(self.host_profile)],
                           profile_build=self.build_profile,
                           build=["missing"],
                           settings=all_settings,
                           env=all_env)

    def conan_create(self, architecture: Architecture, settings: list[str] = [],
                     env: list[str] = []):
        """creates the conan package for the current configuration"""
        print_prefixed(f'creating conan package for architecture {architecture.name}:')
        all_settings = settings + self.settings + [f"arch={architecture.value.conan}"]
        all_env = env + self.env
        self.conan.create(profile_names=[str(self.host_profile)],
                          profile_build=self.build_profile,
                          conanfile_path=str(self.working_directory),
                          settings=all_settings,
                          user=self.conan_user,
                          channel=self.conan_channel,
                          env=all_env)

    @staticmethod
    def _copy_directory(src_dir: Path, target_dir: Path, clean: bool = True):
        print_prefixed(f"Copy directory '{src_dir}' to '{target_dir}'")
        if target_dir.exists() and clean:
            shutil.rmtree(target_dir)
        shutil.copytree(src=src_dir, dst=target_dir, symlinks=True)

    @staticmethod
    def _copy_file(src: Path, dst: Path):
        print_prefixed(f"Copy file '{src}' to '{dst}'")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)

    @staticmethod
    def _clean(directory: Path):
        """deletes the given directory if it exists"""
        if directory.exists():
            shutil.rmtree(directory)

    @staticmethod
    def _execute(command: str, arguments: list[str], working_dir: Path = Path(os.getcwd())) -> int:
        cwd = os.getcwd()
        os.chdir(working_dir)
        full_command = f'{command} {" ".join(arguments)}'
        print_prefixed(f"Executing command '{full_command}'")
        result = os.system(full_command)
        os.chdir(cwd)
        return result
