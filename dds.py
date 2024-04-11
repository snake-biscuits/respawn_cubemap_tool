# https://learn.microsoft.com/en-us/windows/win32/direct3ddds/dds-file-layout-for-cubic-environment-maps
from __future__ import annotations
import enum
import struct
from typing import Any, List, Tuple, Union


# copied from vtf.py, I'm too tired to wire this up properly
def read_struct(file, format_: str) -> Union[Any, List[Any]]:
    out = struct.unpack(format_, file.read(struct.calcsize(format_)))
    if len(out) == 1:
        out = out[0]
    return out


def write_struct(file, format_: str, *args):
    file.write(struct.pack(format_, *args))


class DXGI(enum.Enum):
    BC6H_UF16 = 0x5F  # the only format we care about


class DDS:
    filename: str
    # header
    size: Tuple[int, int]  # width, height
    num_mipmaps: int
    # DX10 extended header
    dxgi_format: DXGI
    resource_dimension: int  # always 3?
    misc_flag: int  # TODO: enum
    # pixel data
    mipmaps: List[bytes]

    def __repr__(self) -> str:
        major, minor = self.version
        version = f"v{major}.{minor}"
        width, height = self.size
        size = f"{width}x{height}"
        return f"<VTF {version} '{self.filename}' {size} {self.format.name} flags={self.flags.name}>"

    # NOTE: sizeof(header) + sizeof(extended_header) = 148 (start of mips)
    def read(self, offset: int, length: int) -> bytes:
        """pull data after initial header parse"""
        with open(self.filename, "rb") as dds_file:
            dds_file.seek(offset)
            assert dds_file.tell() == offset, f"offset is past EOF ({dds_file.tell()})"
            out = dds_file.read(length)
            assert dds_file.tell() == offset + length, f"read past EOF ({dds_file.tell()})"
        return out

    @classmethod
    def from_file(cls, filename: str) -> DDS:
        out = cls()
        out.filename = filename
        with open(filename, "rb") as dds_file:
            # header
            assert dds_file.read(4) == b"DDS "
            assert read_struct(dds_file, "2I") == (0x7C, 0x000A1007)  # version?
            out.size = read_struct(dds_file, "2I")
            assert read_struct(dds_file, "2I") == (0x00010000, 0x01)  # pitch / linsize?
            out.num_mipmaps = read_struct(dds_file, "I")
            assert dds_file.read(44) == b"\0" * 44
            assert read_struct(dds_file, "2I") == (0x20, 0x04)  # don't know, don't care
            # DX10 extended header
            assert dds_file.read(4) == b"DX10"
            assert dds_file.read(20) == b"\0" * 20
            assert read_struct(dds_file, "I") == 0x00401008  # idk, some flags?
            assert dds_file.read(16) == b"\0" * 16
            out.dxgi_format = DXGI(read_struct(dds_file, "I"))
            out.resource_dimension = read_struct(dds_file, "I")
            out.misc_flag = read_struct(dds_file, "I")
            out.array_size = read_struct(dds_file, "I")
            assert dds_file.read(4) == b"\0" * 4  # reserved
            # pixel data
            if out.dxgi_format == DXGI.BC6H_UF16:
                assert out.array_size == 1  # pls no
                mip_sizes = [max(1 << i, 4) ** 2 for i in range(out.num_mipmaps)]
                out.mipmaps = list()
                for mip_size in reversed(mip_sizes):
                    out.mipmaps.append(dds_file.read(mip_size))
                out.mipmaps = out.mipmaps[::-1]  # biggest first
            else:
                raise NotImplementedError("compression size unknown, cannot extract mipmaps")
        return out

    def save_as(self, filename: str):
        with open(filename, "wb") as dds_file:
            # header
            write_struct(dds_file, "4s", b"DDS ")
            write_struct(dds_file, "2I", 0x7C, 0x000A1007)  # version?
            write_struct(dds_file, "2I", *self.size)
            write_struct(dds_file, "2I", 0x00010000, 0x01)  # pitch / linsize?
            write_struct(dds_file, "I", self.num_mipmaps)
            write_struct(dds_file, "44s", b"\0" * 44)
            write_struct(dds_file, "2I", 0x20, 0x04)  # don't know, don't care
            # DX10 extended header
            write_struct(dds_file, "4s", b"DX10")
            write_struct(dds_file, "20s", b"\0" * 20)
            assert read_struct(dds_file, "I") == 0x00401008  # idk, some flags?
            assert dds_file.read(16) == b"\0" * 16
            write_struct(dds_file, "I", self.dxgi_format.value)
            write_struct(dds_file, "I", self.resource_dimension)
            write_struct(dds_file, "I", self.misc_flag)
            write_struct(dds_file, "I", self.array_size)
            assert dds_file.read(4) == b"\0" * 4  # reserved
            # pixel data
            assert self.array_size == 1  # pls no
            for i in reversed(range(self.num_mipmaps)):
                dds_file.write(self.mipmaps[i])
