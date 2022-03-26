from enum import Enum
from collections import namedtuple


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


class BuildConfiguration(ArgparseEnum):
    """enum of all possible build configurations."""
    release = 'Release'
    debug = 'Debug'


ArchitectureDetails = namedtuple('ArchitectureName', 'conan android windows bit')


class Architecture(ArgparseEnum):
    """enum with all possible architectures that one can build for, and the names for them on each target platform"""
    x86_64 = ArchitectureDetails(conan='x86_64', android='x86_64', windows='win10-x64', bit='64')
    x86 = ArchitectureDetails(conan='x86', android='x86', windows='win10-x86', bit='32')
    armv8 = ArchitectureDetails(conan='armv8', android='arm64-v8a', windows='win10-arm64', bit='64')
    armv7 = ArchitectureDetails(conan='armv7', android='armeabi-v7a', windows='win10-arm', bit='32')


class PackageType(ArgparseEnum):
    xcframework = 'XCFramework'
    swiftpackage = 'Swift Package'
    conan = 'Conan'
    aar = 'Android Archive'
    nuget = 'NuGet'
