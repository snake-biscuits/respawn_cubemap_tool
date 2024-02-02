# https://developer.valvesoftware.com/wiki/VTF_(Valve_Texture_Format)
# https://github.com/NeilJed/VTFLib/blob/main/VTFLib/VTFFormat.h
from __future__ import annotations
import enum
import struct
from typing import Any, Dict, List, Tuple, Union


class Format(enum.Enum):
    NONE = -1
    RGBA8888 = 0
    ABGR8888 = 2
    RGB888 = 3
    BGR888 = 4
    RGB565 = 5
    I8 = 6
    IA88 = 7
    P8 = 8
    A8 = 9
    RGB888_BLUESCREEN = 10
    BGR888_BLUESCREEN = 11
    ARGB8888 = 12
    BGRA8888 = 13
    DXT1 = 14
    DXT3 = 15
    DXT5 = 16
    BGRX8888 = 17
    BGR565 = 18
    BGRX5551 = 19
    BGRA4444 = 20
    DXT1_ONE_BIT_ALPHA = 21
    BGRA5551 = 22
    UV88 = 23
    UVWQ8888 = 24
    RGBA16161616F = 25
    RGBA16161616 = 26
    UVLX8888 = 27
    ...
    BC6H_UF16 = 66  # cubemaps.hdr.vtf only


class Flags(enum.IntFlag):
    POINT_SAMPLE = 0x00000001
    TRILINEAR = 0x00000002
    CLAMP_S = 0x00000004
    CLAMP_T = 0x00000008
    ANISOTROPIC = 0x00000010
    HINT_DXT5 = 0x00000020
    PWL_CORRECTED = 0x00000040
    NORMAL = 0x00000080
    NO_MIP = 0x00000100
    NO_LOD = 0x00000200
    ALL_MIPS = 0x00000400
    PROCEDURAL = 0x00000800
    ONE_BIT_ALPHA = 0x00001000
    EIGHT_BIT_ALPHA = 0x00002000
    ENVMAP = 0x00004000
    RENDER_TARGET = 0x00008000
    DEPTH_RENDER_TARGET = 0x00010000
    NO_DEBUG_OVERRIDE = 0x00020000
    SINGLE_COPY = 0x00040000
    PRE_SRGB = 0x00080000
    NO_DEPTH_BUFFER = 0x00800000
    CLAMP_U = 0x02000000
    VERTEX_TEXTURE = 0x04000000
    SSBUMP = 0x08000000
    BORDER = 0x20000000


def read_struct(file, format_: str) -> Union[Any, List[Any]]:
    out = struct.unpack(format_, file.read(struct.calcsize(format_)))
    if len(out) == 1:
        out = out[0]
    return out


class Resource:
    tag: bytes
    flags: int  # 0x2 = NO_DATA
    offset: int

    valid_tags = {
        b"\x01\x00\x00": "Thumbnail",
        b"\x30\x00\x00": "Image Data",
        b"\x10\x00\x00": "Sprite Sheet",
        b"CRC": "Cyclic Redundancy Check",
        b"CMA": "Cubemap Mystery Attributes",
        b"LOD": "Level of Detail Information",
        b"TSO": "Extended Flags",
        b"KVD": "Key Values Data"}

    def __init__(self, tag, flags, offset):
        self.tag = tag
        assert tag in self.valid_tags, tag
        if tag == b"CRC":
            assert flags == 0x02, "CRC Resource should only hold checksum"
            self.checksum = offset
        else:
            self.flags = flags
            self.offset = offset

    def __repr__(self) -> str:
        tag_type = self.valid_tags[self.tag]
        if self.tag == b"CRC":
            return f"<Resource | {tag_type} checksum=0x{self.checksum:08X}>"
        else:
            return f"<Resource | {tag_type} flags=0x{self.flags:02X} offset={self.offset}>"

    @classmethod
    def from_stream(cls, vtf_file) -> Resource:
        return cls(*read_struct(vtf_file, "3sBI"))


class VTF:
    filename: str
    version: Tuple[int, int]
    header_size: int
    size: Tuple[int, int]  # width, height
    flags: Flags
    num_frames: int
    first_frame: int
    reflectivity: Tuple[float, float, float]  # rgb
    bumpmap_scale: int
    format: Format
    mipmap_count: int
    low_res_format: Format
    low_res_size: Tuple[int, int]  # width, height
    resources: List[Resource]
    # pull the textures yourself
    # -- header to locate
    # -- .read() to extract

    def __repr__(self) -> str:
        major, minor = self.version
        version = f"v{major}.{minor}"
        width, height = self.size
        size = f"{width}x{height}"
        return f"<VTF {version} '{self.filename}' {size} {self.format.name} flags={self.flags.name}>"

    def read(self, offset: int, length: int) -> bytes:
        """pull data after initial header parse"""
        with open(self.filename, "rb") as vtf_file:
            vtf_file.seek(offset)
            assert vtf_file.tell() == offset, f"offset is past EOF ({vtf_file.tell()})"
            out = vtf_file.read(length)
            assert vtf_file.tell() == offset + length, f"read past EOF ({vtf_file.tell()})"
        return out

    @classmethod
    def from_file(cls, filename) -> VTF:
        out = cls()
        out.filename = filename
        with open(filename, "rb") as vtf_file:
            assert vtf_file.read(4) == b"VTF\0"
            out.version = read_struct(vtf_file, "2I")
            if out.version != (7, 5):
                raise NotImplementedError(f"v{out.version[0]}.{out.version[1]} is not supported!")
            out.header_size = read_struct(vtf_file, "I")
            out.size = read_struct(vtf_file, "2H")
            out.flags = Flags(read_struct(vtf_file, "I"))
            out.num_frames, out.first_frame = read_struct(vtf_file, "2H")
            assert vtf_file.read(4) == b"\0" * 4
            out.reflectivity = read_struct(vtf_file, "3f")
            assert vtf_file.read(4) == b"\0" * 4
            out.bumpmap_scale = read_struct(vtf_file, "f")
            out.format = Format(read_struct(vtf_file, "I"))
            out.num_mipmaps = read_struct(vtf_file, "B")
            out.low_res_format = Format(read_struct(vtf_file, "i"))  # always DXT1
            out.low_res_size = read_struct(vtf_file, "2B")
            # v7.2+
            out.mipmap_depth = read_struct(vtf_file, "H")
            # v7.3+
            assert vtf_file.read(3) == b"\0" * 3
            num_resources = read_struct(vtf_file, "I")
            assert vtf_file.read(8) == b"\0" * 8
            resources = [Resource.from_stream(vtf_file) for i in range(num_resources)]
            out.resources = {Resource.valid_tags[r.tag]: r for r in resources}
            assert vtf_file.tell() == out.header_size
        return out

    @property
    def as_json(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "header_size": self.header_size,
            "size": self.size,
            "flags": self.flags.name,
            "num_frames": self.num_frames,
            "first_frame": self.first_frame,
            "reflectivity": self.reflectivity,
            "bumpmap_scale": self.bumpmap_scale,
            "format": self.format.name,
            "num_mipmap": self.num_mipmaps,
            "low_res_format": self.low_res_format.name,
            "low_res_size": self.low_res_size,
            "mipmap_depth": self.mipmap_depth,
            "resources": {k: str(v) for k, v in self.resources.items()}}


class CMA:
    data: List[int]

    def __repr__(self) -> str:
        return f"<CMA with {len(self.data)} entries at 0x{id(self):012X}>"

    @classmethod
    def from_vtf(cls, vtf: VTF):
        assert "Cubemap Mystery Attributes" in vtf.resources
        resource = vtf.resources["Cubemap Mystery Attributes"]
        out = cls()
        if resource.flags == 0x02:  # no data
            out.data = [resource.offset]
        else:
            num_ints = vtf.num_frames + 1
            size, *out.data = struct.unpack(f"{num_ints}I", vtf.read(resource.offset, 4 * num_ints))
            assert size == vtf.num_frames * 4
        return out

    @property
    def as_json(self) -> List[str]:
        return [f"0x{x:08X}" for x in self.data]


def extract_cubemap_mipmaps(vtf: VTF) -> Dict[Tuple[int, int, int], bytes]:
    """{(mip_index, cubemap_index, side_index): mip_bytes}"""
    assert Flags.ENVMAP in vtf.flags
    assert vtf.format == Format.BC6H_UF16
    assert vtf.size == (256, 256)
    assert vtf.low_res_format == Format.NONE
    assert vtf.low_res_size == (0, 0)
    assert "Cubemap Mystery Attributes" in vtf.resources
    assert "Image Data" in vtf.resources
    assert vtf.first_frame == 0
    # mip.X-side.0-cubemap.0 ... mip.0-side.5-cubemap.X
    offset = vtf.resources["Image Data"].offset
    mip_sizes = [max(1 << i, 4) ** 2 for i in range(vtf.num_mipmaps)]
    mipmaps = dict()
    for mip_index in range(vtf.num_mipmaps):
        for cubemap_index in range(vtf.num_frames):
            for side_index in range(6):
                mipmaps[(mip_index, cubemap_index, side_index)] = vtf.read(offset, mip_sizes[mip_index])
                offset += mip_sizes[mip_index]
    return mipmaps


# https://learn.microsoft.com/en-us/windows/win32/direct3ddds/dds-file-layout-for-cubic-environment-maps
dds_header = [
    b"DDS ", 0x7C, 0x000A1007,
    256, 256, 0x00010000, 0x01, 9,  # height, width, pitch_or_linsize, num_mipmaps
    *(0,) * 11, 0x20, 0x04,
    b"DX10", *(0,) * 5,
    0x00401008, *(0,) * 4,
    # DX10 extended header
    0x5F, 0x03, 0x00, 0x01, 0x00]  # dxgi_format, resource_dimension, misc_flag, array_size, reserved
# NOTE: should be misc_flag, array_size = 0x04, 6
# -- however this breaks in paint.net & that's what I'm using to view .dds files
# -- so 1 .dds per cubemap side it is

dds_header_bytes = struct.pack("4s20I4s15I", *dds_header)


def save_cubemap_mipmaps_as_dds(vtf: VTF):
    mipmaps = extract_cubemap_mipmaps(vtf)
    # cubemap.0-side.0-mip.0 ... cubemap.X-side.5-mip.X
    for cubemap_index, uuid in enumerate(CMA.from_vtf(vtf).as_json):
        for side_index in range(6):
            with open(f"{vtf.filename}.{cubemap_index}.{uuid}.{side_index}.dds", "wb") as dds_file:
                dds_file.write(dds_header_bytes)
                for mip_index in reversed(range(vtf.num_mipmaps)):
                    dds_file.write(mipmaps[(mip_index, cubemap_index, side_index)])
