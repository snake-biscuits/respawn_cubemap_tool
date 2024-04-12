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
    print("-===- regen systems online -===-")

    # IMPORT bsp_tool
    bsp_tool_path = get_filepath("bsp_tool", verify=os.path.isdir)
    import sys
    sys.path.insert(0, bsp_tool_path)
    import bsp_tool

    def verify_bsp(filepath: str):
        if os.path.isfile(filepath):
            try:
                bsp = bsp_tool.load_bsp(filepath)
            except Exception:
                return False
            return (bsp.file_magic == b"rBSP" and bsp.version == 29)
        return False

    # OPEN r1 .bsp
    bsp_path = get_filepath("Titanfall 1 .bsp", verify_bsp)
    bsp = bsp_tool.load_bsp(bsp_path)
    if bsp.headers["CUBEMAPS"].length == 0:
        print("!!! ERROR !!! .bsp has no cubemaps")
        exit()

    cubemap_dir = f"materials/maps/{bsp.filename[:-4]}"
    cubemap_filenames = [
        f"{cubemap_dir}/c{int(c.origin.x)}_{int(c.origin.y)}_{int(c.origin.z)}.hdr.vtf"
        for c in bsp.CUBEMAPS]

    import shutil

    def flush_dir(dir_path: str):
        """WARNING: be careful not to `rm -rf /` yourself"""
        if os.path.isdir(dir_path):
            shutil.rmtree(dir_path)
        os.mkdir(dir_path)

    # EXTRACT r1 .vtf & CONVERT TO .tga
    import vtf
    from PIL import Image  # pip install pillow
    print("~~ extracting cubemaps into working directory ~~")
    flush_dir("./r1/")  # old PakFile
    # TODO: flush ./r1/ contents
    cubemap_extracted_filenames = list()
    for cubemap_index, cubemap_name in enumerate(cubemap_filenames):
        bsp.PAKFILE.extract(cubemap_name, "./r1/")
        r1_vtf = vtf.VTF.from_file(os.path.join("./r1/", cubemap_name))
        r1_mips = vtf.extract_cubemap_mipmaps_r1(r1_vtf)
        for face_index in range(6):  # face index
            mip_bytes = r1_mips[(6, 0, face_index)]  # 6th mip is full size (64x64)
            # NOTE: texconv handles BC6H_UF16 compression, resizing & mip generation
            mip_image = Image.frombytes("RGBA", r1_vtf.size, mip_bytes, "raw")
            # TODO: mutate alpha
            # -- RGB * 50% of Alpha (Opaque)
            # try: https://pillow.readthedocs.io/en/stable/_modules/PIL/ImageChops.html
            extracted_filename = os.path.join("./r1/", cubemap_dir, f"cubemap.{cubemap_index}.{face_index}.tga")
            mip_image.save(extracted_filename)
            cubemap_extracted_filenames.append(extracted_filename)

    # r1 .tga -> r2 .dds
    print("https://github.com/microsoft/DirectXTex/wiki/Texconv")
    texconv_path = get_filepath("texconv")
    with open("./r1/cubemaps.txt", "w") as flist:
        flist.write("\n".join(cubemap_extracted_filenames) + "\n")
    import subprocess
    subprocess.run(f"{texconv_path} -f BC6H_UF16 -w 256 -h 256 -flist ./r1/cubemaps.txt", shell=True)

    # MOVE .dds -> ./r1/
    for tga_filename in cubemap_extracted_filenames:
        dds_filename = os.path.basename(tga_filename).replace(".tga", ".dds")
        os.rename(f"./{dds_filename}", f"./r1/{cubemap_dir}/{dds_filename}")

    # READ .DDS MIPMAPS
    import dds
    r2_mips = dict()
    # ^ {(mipmap, cubemap, face): mip_bytes}
    for tga_filename in cubemap_extracted_filenames:
        dds_filename = tga_filename.replace(".tga", ".dds")
        cubemap_index, face_index = map(int, dds_filename.split(".")[2:4])  # ./*/cubemap.C.F.dds
        r1_dds = dds.DDS.from_file(dds_filename)
        assert r1_dds.format == dds.DXGI.BC6H_UF16
        assert r1_dds.num_mipmaps == 9
        assert r1_dds.size == (256, 256)
        for i in range(9):
            r2_mips[(i, cubemap_index, face_index)] = r1_dds.mipmaps[i]
            # NOTE: mipmaps are reverse order in .dds
            # -- flipped the order in the DDS class so they line up

    # GENERATE r2/.../cubemaps.hdr.vtf
    flush_dir("./r2/")  # new PakFile
    r2_vtf = vtf.VTF()
    # TODO: set the entire .vtf header
    r2_vtf.version = (7, 5)
    r2_vtf.size = (256, 256)
    r2_vtf.flags = vtf.Flags.CLAMP_S | vtf.Flags.CLAMP_T | vtf.Flags.NO_LOD | vtf.Flags.ENVMAP
    r2_vtf.num_frames = len(bsp.CUBEMAPS)
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
    r2_vtf.save_as(os.path.join("./r2/", cubemap_dir, "cubemaps.hdr.vtf"))

    # GENERATE PAKFILE
    # p0358 has the exact PakFile spec figured out:
    # -- https://github.com/MRVN-Radiant/MRVN-Radiant/issues/55#issuecomment-2016653142
    pakfile_name = f"{bsp.filename[:-4]}.PakFile.zip"
    if os.path.exists(pakfile_name):
        os.remove(pakfile_name)
    subprocess.run(f"zip -0 --recurse-paths --no-dir-entries --junk-sfx --filesync -X ../{pakfile_name} .", cwd="./r2/")

    # TODO: overwrite PakFile in a target .bsp

    print("-===- regen complete -===-")
