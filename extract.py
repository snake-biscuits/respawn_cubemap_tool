import dds
import vtf


dds_header = [
    b"DDS ", 0x7C, 0x000A1007,
    256, 256, 0x00010000, 0x01, 9,  # height, width, pitch_or_linsize, num_mipmaps
    *(0,) * 11, 0x20, 0x04,
    b"DX10", *(0,) * 5,
    0x00401008, *(0,) * 4,
    # DX10 extended header
    0x5F, 0x03, 0x00, 0x01, 0x00]  # format, resource_dimension, misc_flag, array_size, reserved
# NOTE: should be misc_flag, array_size = 0x04, 6
# -- however this breaks in paint.net & that's what I'm using to view .dds files
# -- so 1 .dds per cubemap side it is


# TODO: r1 cubemap mip0s -> .tga w/ pillow


def save_r2_cubemaps_as_dds(vtf_: vtf.VTF):
    assert vtf_.format == vtf.Format.BC6H_UF16
    # cubemap.0-side.0-mip.0 ... cubemap.X-side.5-mip.X
    for cubemap_index, uuid in enumerate(vtf.CMA.from_vtf(vtf).as_json):
        for side_index in range(6):
            dds_ = dds.DDS()
            dds_.size = vtf_.size
            dds_.num_mipmaps = vtf_.num_mipmaps
            dds_.format = dds.Format.BC6H_UF16
            dds_.resource_dimension = 3  # idk man
            dds_.misc_flag = 0x00
            dds_.array_size = 1
            for mip_index in reversed(range(vtf.num_mipmaps)):
                dds_.mipmaps[mip_index] = vtf.mipmaps[(mip_index, cubemap_index, side_index)]
            dds_.save_as(f"{vtf_.filename}.{cubemap_index}.{uuid}.{side_index}.dds")
