# https://developer.valvesoftware.com/wiki/VTF_(Valve_Texture_Format)
# https://github.com/NeilJed/VTFLib/blob/main/VTFLib/VTFFormat.h
from __future__ import annotations
import enum
import io
import os
import struct
from typing import Any, Dict, List, Tuple, Union


class Format(enum.Enum):
    NONE = -1
    RGBA_8888 = 0
    ABGR_8888 = 1
    RGB_888 = 2
    BGR_888 = 3
    RGB_565 = 4
    I8 = 5
    IA_88 = 6
    P_8 = 7
    A_8 = 8
    RGB_888_BLUESCREEN = 9
    BGR_888_BLUESCREEN = 10
    ARGB_8888 = 11
    BGRA_8888 = 12
    DXT1 = 13
    DXT3 = 14
    DXT5 = 15
    BGRX_8888 = 16
    BGR_565 = 17
    BGRX_5551 = 18
    BGRA_4444 = 19
    DXT1_ONE_BIT_ALPHA = 20
    BGRA_5551 = 21
    UV_88 = 22
    UVWQ_8888 = 23
    RGBA_16161616F = 24
    RGBA_16161616 = 25
    UVLX_8888 = 26
    ...
    BC6H_UF16 = 66  # r2 / r5 cubemaps.hdr.vtf only


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


def write_struct(file, format_: str, *args):
    file.write(struct.pack(format_, *args))


class Resource:
    tag: bytes
    flags: int  # 0x2 = NO_DATA
    offset: int

    valid_tags = {
        b"\x01\x00\x00": "Thumbnail",
        b"\x30\x00\x00": "Image Data",
        b"\x10\x00\x00": "Sprite Sheet",
        b"CRC": "Cyclic Redundancy Check",
        b"CMA": "Cubemap Multiply Ambient",
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

    def as_bytes(self) -> bytes:
        return struct.pack("3sBI", self.tag, self.flags, self.offset)


class VTF:
    filename: str
    version: Tuple[int, int]
    size: Tuple[int, int]  # width, height
    flags: Flags
    num_frames: int
    first_frame: int
    reflectivity: Tuple[float, float, float]  # rgb
    bumpmap_scale: int
    format: Format
    num_mipmaps: int
    low_res_format: Format
    low_res_size: Tuple[int, int]  # width, height
    resources: List[Resource]
    mipmaps: Dict[Tuple[int, int, int], bytes]
    # ^ {(mip_index, cubemap_index, side_index): raw_mipmap_data}
    cma: Union[None, CMA]

    def __init__(self):
        self.mipmaps = dict()
        # defaults
        self.filename = "untitled.vtf"
        self.version = (7, 5)
        self.format = Format.NONE
        self.flags = Flags(0x00)  # self.flags.name will be a blank string
        self.size = (0, 0)
        self.cma = None

    def __repr__(self) -> str:
        major, minor = self.version
        version = f"v{major}.{minor}"
        width, height = self.size
        size = f"{width}x{height}"
        return f"<VTF {version} '{self.filename}' {size} {self.format.name} flags={self.flags.name}>"

    @classmethod
    def from_bytes(cls, raw_vtf: bytes) -> VTF:
        return cls.from_stream(io.BytesIO(raw_vtf))

    @classmethod
    def from_file(cls, filename: str) -> VTF:
        with open(filename, "rb") as vtf_file:
            out = cls.from_stream(vtf_file)
        out.filename = filename
        return out

    @classmethod
    def from_stream(cls, vtf_file: io.BytesIO) -> VTF:
        out = cls()
        assert vtf_file.read(4) == b"VTF\0"
        out.version = read_struct(vtf_file, "2I")
        if out.version != (7, 5):
            raise NotImplementedError(f"v{out.version[0]}.{out.version[1]} is not supported!")
        header_size = read_struct(vtf_file, "I")
        out.size = read_struct(vtf_file, "2H")
        out.flags = Flags(read_struct(vtf_file, "I"))
        out.num_frames, out.first_frame = read_struct(vtf_file, "2H")
        assert vtf_file.read(4) == b"\0" * 4
        out.reflectivity = read_struct(vtf_file, "3f")
        assert vtf_file.read(4) == b"\0" * 4
        out.bumpmap_scale = read_struct(vtf_file, "f")
        out.format = Format(read_struct(vtf_file, "I"))
        out.num_mipmaps = read_struct(vtf_file, "B")
        out.low_res_format = Format(read_struct(vtf_file, "i"))
        out.low_res_size = read_struct(vtf_file, "2B")
        # v7.2+
        out.mipmap_depth = read_struct(vtf_file, "H")
        # v7.3+
        assert vtf_file.read(3) == b"\0" * 3
        num_resources = read_struct(vtf_file, "I")
        assert vtf_file.read(8) == b"\0" * 8
        resources = [Resource.from_stream(vtf_file) for i in range(num_resources)]
        out.resources = {Resource.valid_tags[r.tag]: r for r in resources}
        assert vtf_file.tell() == header_size
        # CMA
        if "Cubemap Multiply Ambient" in out.resources:
            out.cma = CMA.from_vtf_stream(out, vtf_file)
            vtf_file.seek(header_size)
        # mipmaps
        assert Flags.ENVMAP in out.flags
        assert out.low_res_format == Format.NONE
        assert out.low_res_size == (0, 0)
        assert out.first_frame == 0
        assert "Image Data" in out.resources
        vtf_file.seek(out.resources["Image Data"].offset)
        # TODO: r1o 32x32 Format.DXT5 "cubemapdefault.vtf" (LDR)
        # TODO: r1o 32x32 Format.RGBA_16161616F "cubemapdefault.hdr.vtf" (HDR)
        # -- mip bytes are all zero afaik
        if out.format == Format.RGBA_8888 and out.size == (64, 64):  # Titanfall
            mip_sizes = [(1 << i) ** 2 * 4 for i in range(out.num_mipmaps)]
        elif out.format == Format.BC6H_UF16 and out.size == (256, 256):  # Titanfall 2 / Apex Legends
            mip_sizes = [max(1 << i, 4) ** 2 for i in range(out.num_mipmaps)]
        else:
            # TODO: UserWarning("use .read(offset, size) to get the mipmaps yourself")
            return out  # exit early
        # parse mipmaps
        # mip.X-side.0-cubemap.0 ... mip.0-side.5-cubemap.X
        out.mipmaps = {
            (mip_index, cubemap_index, side_index): vtf_file.read(mip_sizes[mip_index])
            for mip_index in range(out.num_mipmaps)
            for cubemap_index in range(out.num_frames)
            for side_index in range(6)}
        # TODO: assert EOF reached
        return out

    @property
    def as_json(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "size": self.size,
            "flags": self.flags.name,
            "num_frames": self.num_frames,
            "first_frame": self.first_frame,
            "reflectivity": self.reflectivity,
            "bumpmap_scale": self.bumpmap_scale,
            "format": self.format.name,
            "num_mipmaps": self.num_mipmaps,
            "low_res_format": self.low_res_format.name,
            "low_res_size": self.low_res_size,
            "mipmap_depth": self.mipmap_depth,
            "resources": {k: str(v) for k, v in self.resources.items()},
            "cma": self.cma.as_json if self.cma is not None else None}

    def save_as(self, filename: str):
        assert self.version == (7, 5)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "wb") as vtf_file:
            # header
            vtf_file.write(b"VTF\0")
            write_struct(vtf_file, "2I", *self.version)
            header_size = 80 + len(self.resources) * 8
            write_struct(vtf_file, "I", header_size)
            write_struct(vtf_file, "2H", *self.size)
            write_struct(vtf_file, "I", self.flags.value)
            write_struct(vtf_file, "2H", self.num_frames, self.first_frame)
            vtf_file.write(b"\0" * 4)
            write_struct(vtf_file, "3f", *self.reflectivity)
            vtf_file.write(b"\0" * 4)
            write_struct(vtf_file, "f", self.bumpmap_scale)
            write_struct(vtf_file, "I", self.format.value)
            write_struct(vtf_file, "B", self.num_mipmaps)
            write_struct(vtf_file, "i", self.low_res_format.value)
            write_struct(vtf_file, "2B", *self.low_res_size)
            # v7.2+
            write_struct(vtf_file, "H", self.mipmap_depth)
            # v7.3+
            vtf_file.write(b"\0" * 3)
            write_struct(vtf_file, "I", len(self.resources))
            vtf_file.write(b"\0" * 8)
            # TODO: verify / calculate resource offsets
            offset = header_size  # vtf_header + 8 bytes per resource
            if "Cyclic Redundancy Check" in self.resources:
                # TODO: save crc32 in self.resources["Cyclic Redundany Check"].offset
                raise NotImplementedError("idk how to generate CRC")
            if "Cubemap Multiply Ambient" in self.resources:
                assert self.cma is not None
                assert len(self.cma.data) == self.num_frames
                if self.num_frames == 1:
                    self.resources["Cubemap Multiply Ambient"].flags = 0x02
                    cma_0 = struct.pack("f", self.cma.data[0])
                    self.resources["Cubemap Multiply Ambient"].offset = cma_0
                else:
                    self.resources["Cubemap Multiply Ambient"].flags = 0x00
                    self.resources["Cubemap Multiply Ambient"].offset = offset
                    offset += (self.num_frames + 1) * 4
            # NOTE: Image Data is always last!
            if "Image Data" in self.resources:
                self.resources["Image Data"].offset = offset
            vtf_file.write(b"".join(r.as_bytes() for r in self.resources.values()))
            assert vtf_file.tell() == header_size
            # write cma
            if self.cma is not None:
                vtf_file.write(self.cma.as_bytes())
            # write mips
            assert "Image Data" in self.resources
            assert self.resources["Image Data"].offset == vtf_file.tell()
            assert Flags.ENVMAP in self.flags
            vtf_file.write(b"".join([  # sorted mips
                self.mipmaps[(mipmap_index, cubemap_index, face_index)]
                for mipmap_index in range(self.num_mipmaps)
                for cubemap_index in range(self.num_frames)
                for face_index in range(6)]))


class CMA:
    """same data as rBSP v48 CUBEMAPS_AMBIENT_RCP"""
    data: List[float]

    def __repr__(self) -> str:
        return f"<CMA with {len(self.data)} entries at 0x{id(self):012X}>"

    def as_bytes(self) -> bytes:
        if len(self.data) == 1:
            return b""
        return struct.pack(f"I{len(self.data)}f", len(self.data) * 4, *self.data)

    @classmethod
    def from_data(cls, *data: List[float]):
        out = cls()
        out.data = data
        return out

    @classmethod
    def from_vtf_stream(cls, vtf: VTF, vtf_file: io.BytesIO):
        resource = vtf.resources["Cubemap Multiply Ambient"]
        out = cls()
        if resource.flags == 0x02:  # no more data to read
            out.data = struct.pack("f", resource.offset.to_bytes(4, "little"))
        else:
            vtf_file.seek(resource.offset)
            size, *out.data = read_struct(vtf_file, f"I{vtf.num_frames}f")
            assert size == vtf.num_frames * 4
        return out

    @property
    def as_json(self) -> List[str]:
        return [f"0x{x:08X}" for x in self.data]
