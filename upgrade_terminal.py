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

    cubemap_dir = "materials/maps/{bsp.filename[:-4]}"
    cubemap_filenames = [
        os.path.join(cubemap_dir, f"c{int(c.origin.x)}_{int(c.origin.y)}_{int(c.origin.z)}.hdr.vtf")
        for c in bsp.CUBEMAPS]

    # EXTRACT r1 .vtf & CONVERT TO .tga
    import vtf
    from PIL import Image  # pip install pillow
    print("~~ extracting cubemaps into working directory ~~")
    os.mkdir("./r1/")  # old PakFile
    cubemap_extracted_filenames = list()
    for i, cubemap_name in enumerate(cubemap_filenames):
        # TODO: extract into ./r1/
        bsp.PAKFILE.extract(cubemap_name, "./r1/")
        r1_vtf = vtf.VTF.from_file(os.path.join("./r1/", cubemap_name))
        r1_mips = vtf.extract_cubemap_mipmaps_r1(r1_vtf)
        for face_index in range(6):  # face index
            mip_bytes = r1_mips[(0, 0, face_index)]
            mip_image = Image.frombytes("RGBA", r1_vtf.size, mip_bytes, "raw")
            # TODO: mutate alpha, if nessecary
            extracted_filename = os.path.join("./r1/", cubemap_dir, f"cubemap.{i}.{face_index}.tga")
            Image.save(extracted_filename)
            cubemap_extracted_filenames.append(extracted_filename)

    # r1 .TGA -> r2 .DDS
    print("https://github.com/microsoft/DirectXTex/wiki/Texconv")
    texconv_path = get_filepath("texconv")
    with open("cubemaps.txt") as flist:
        flist.write("\n".join([cubemap_extracted_filenames]) + "\n")
    import subprocess
    subprocess.run("texconv -f BC6H_UF16 -w 256 -h 256 -m 9 -sealpha -flist cubemaps.txt", shell=True)
    # texconv can do all our conversions for us?
    # -- box compression w/ "-f BC6H_UF16"
    # -- rescale w/ "-w 256 -h 256"
    # -- generate 9 mipmaps w/ "-m 9"
    # -- alpha translation w/ "-sealpha"? (unsure)

    # READ .DDS MIPMAPS
    r2_mips = dict()
    # ^ {(mipmap, cubemap, face): mip_bytes}
    # load each .dds; filename -> dict key
    raise NotImplementedError("UNDER CONSTRUCTION")

    # GENERATE r2/.../cubemaps.hdr.vtf
    os.mkdir("./r2/")  # new PakFile
    r2_vtf = vtf.VTF()
    # TODO: set the entire .vtf header
    r2_vtf.flags = vtf.Flags.ENVMAP  # TODO:  CLAMP_S etc.
    r2_vtf.format = vtf.Format.BC6H_UF16
    r2_vtf_image_data = b"".join([  # sorted mips
        r2_mips[(mi, ci, fi)]
        for mi in range(9)
        for ci in range(len(bsp.CUBEMAPS))
        for fi in range(6)])
    # TODO: insert image data into VTF
    r2_vtf.save_as(os.path.join("./r2/", cubemap_dir, "cubemaps.hdr.vtf"))

    # GENERATE PAKFILE
    # p0358 has the exact PakFile spec figured out:
    # -- https://github.com/MRVN-Radiant/MRVN-Radiant/issues/55#issuecomment-2016653142
    pakfile_name = f"{bsp.filename[:-4]}.PakFile.zip"
    while os.path.exists(pakfile_name):
        print(f"ERROR: '{pakfile_name}' already exists!")
        input(f"To Continue: delete '{pakfile_name}' and press ENTER (CTRL+C to Cancel)")
    subprocess.run(f"zip -0 --recurse-paths --no-dir-entries --junk-sfx --filesync -X ./{pakfile_name} ./r2/")
    # TODO: overwrite PakFile in a target .bsp

    print("-===- regen complete -===-")
