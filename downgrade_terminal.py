"""convert Apex Legends cubemaps_hdr.dds -> cubemaps.hdr.vtf"""
import os


def get_filepath(name: str, verify=os.path.isfile) -> str:
    out = None
    while out is None:
        out = input(f"Enter {name} path: ")
        print("Verifying ...", end="")
        if verify(out):
            print(" PASS")
        else:
            print(" FAIL")
            out = None
    return out


if __name__ == "__main__":
    import dds
    import vtf

    print("-===- regen systems online -===-")

    # READ cubemaps_hdr.dds
    # NOTE: could extract from mp_whatever.bsp.0028.bsp_lump
    r5_dds = dds.DDS.from_file(get_filepath("cubemaps_hdr.dds"))
    r2_mips = dict()
    # ^ {(mipmap, cubemap, face): mip_bytes}
    assert r5_dds.format == dds.DXGI.BC6H_UF16
    assert r5_dds.num_mipmaps == 9
    assert r5_dds.resource_dimension == 3
    assert r5_dds.size == (256, 256)
    assert len(r5_dds.mipmaps) == r5_dds.array_size * r5_dds.num_mipmaps
    for array_index in range(r5_dds.array_size):
        for mip_index in range(r5_dds.num_mipmaps):
            cubemap_index = array_index // 6
            face_index = array_index % 6
            r5_mip = r5_dds.mipmaps[array_index * r5_dds.num_mipmaps + mip_index]
            r2_mips[(mip_index, cubemap_index, face_index)] = r5_mip
            # NOTE: mipmaps are reverse order in .dds
            # -- flipped the order in the DDS class so they line up

    # GENERATE cubemaps.hdr.vtf
    r2_vtf = vtf.VTF()
    # TODO: set the entire .vtf header
    r2_vtf.version = (7, 5)
    r2_vtf.size = (256, 256)
    r2_vtf.flags = vtf.Flags.CLAMP_S | vtf.Flags.CLAMP_T | vtf.Flags.NO_LOD | vtf.Flags.ENVMAP
    r2_vtf.num_frames = r5_dds.array_size // 6
    r2_vtf.first_frame = 0
    r2_vtf.reflectivity = (0.2, 0.2, 0.2)
    r2_vtf.bumpmap_scale = 1.0
    r2_vtf.format = vtf.Format.BC6H_UF16
    r2_vtf.num_mipmaps = 9
    r2_vtf.low_res_format = vtf.Format.NONE
    r2_vtf.low_res_size = (0, 0)
    r2_vtf.mipmap_depth = 1
    r2_vtf.resources = {
        "Image Data": vtf.Resource(tag=b"\x30\x00\x00", flags=0x00, offset=None)}
    # NOTE: vtf.VTF.save_as will calculate the correct offset
    # NOTE: ignoring CRC & CMA for now
    header_size = 80 + len(r2_vtf.resources) * 8
    r2_vtf.resources["Image Data"].offset = header_size
    r2_vtf.mipmaps = r2_mips
    # NOTE: should be mounted in `material/maps/mp_whatever/cubemaps.hdr.vtf`
    r2_vtf.save_as("./cubemaps.hdr.vtf")

    print("-===- regen complete -===-")
