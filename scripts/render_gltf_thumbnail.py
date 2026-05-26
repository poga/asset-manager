"""Headless glTF/GLB thumbnail renderer for Blender.

Invocation:
  blender -b -P scripts/render_gltf_thumbnail.py -- <input> <output> [size]
"""

import math
import sys

import bpy
from mathutils import Vector


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def import_model(path):
    bpy.ops.import_scene.gltf(filepath=path)
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def compute_bounds(objs):
    coords = []
    for obj in objs:
        for v in obj.bound_box:
            coords.append(obj.matrix_world @ Vector(v))
    if not coords:
        return None
    return Vector(map(min, zip(*coords))), Vector(map(max, zip(*coords)))


def setup_camera(min_co, max_co):
    center = (min_co + max_co) / 2
    diag = (max_co - min_co).length
    if diag < 0.001:
        diag = 1.0
    cam_data = bpy.data.cameras.new("ThumbCam")
    cam_obj = bpy.data.objects.new("ThumbCam", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj
    distance = diag * 1.6
    cam_obj.location = center + Vector((distance * 0.7, -distance * 0.7, distance * 0.5))
    cam_obj.rotation_euler = (center - cam_obj.location).to_track_quat("-Z", "Y").to_euler()


def setup_lighting():
    light = bpy.data.lights.new("Sun", type="SUN")
    light.energy = 4.0
    obj = bpy.data.objects.new("Sun", light)
    bpy.context.scene.collection.objects.link(obj)
    obj.rotation_euler = (math.radians(50), math.radians(20), math.radians(35))


def render(out_path, size):
    scn = bpy.context.scene
    scn.render.engine = "BLENDER_WORKBENCH"
    scn.display.shading.light = "STUDIO"
    scn.display.shading.color_type = "TEXTURE"
    scn.display.render_aa = "8"
    scn.render.film_transparent = True
    scn.render.resolution_x = size
    scn.render.resolution_y = size
    scn.render.image_settings.file_format = "PNG"
    scn.render.image_settings.color_mode = "RGBA"
    scn.render.filepath = out_path
    bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv
    if "--" not in argv:
        raise SystemExit("usage: blender -b -P render_gltf_thumbnail.py -- input output [size]")
    args = argv[argv.index("--") + 1:]
    in_path, out_path = args[0], args[1]
    size = int(args[2]) if len(args) > 2 else 256

    clear_scene()
    objs = import_model(in_path)
    bounds = compute_bounds(objs)
    if not bounds:
        raise SystemExit("no mesh bounds in imported model")
    setup_camera(*bounds)
    setup_lighting()
    render(out_path, size)


main()
