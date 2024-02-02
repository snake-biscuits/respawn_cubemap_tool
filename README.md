# respawn_cubemap_vtf_tool

Tools for extracting `materials/maps/*/cubemaps.hdr.vtf` files
Can be used to pull cubemap textures from Titanfall 2 & Apex Legends maps


## Usage

```python
import zipfile
with zipfile.ZipFile("maps/mp_lobby.bsp.0028.bsp_lump") as pakfile:
    pakfile.extractall()  # materials/maps/mp_lobby/cubemaps.hdr.vtf

import vtf
cubemap_vtf = vtf.VTF.from_file("materials/maps/mp_lobby/cubemaps.hdr.vtf")
vtf.save_cubemaps_as_dds(cubemap_vtf)
# materials/maps/mp_lobby/cubemaps.hdr.vtf.cubemap_index.cma_hash.side_index.dds
# -- materials/maps/mp_lobby/cubemaps.hdr.vtf.0.*.0.dds etc.

import enum
class CubemapSide(enum.Enum):
    """Cubemap Side Order"""
    RIGHT = 0  # +X
    LEFT = 1  # -X
    BACK = 2  # +Y
    FRONT = 3  # -Y
    UP = 4  # +Z
    DOWN = 5  # -Z
# NOTE: sides are flipped and rotated to be folded into a "net"
```
