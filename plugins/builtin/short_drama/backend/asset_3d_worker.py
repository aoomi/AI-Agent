#!/usr/bin/env python3
"""Headless TripoSR -> Blender asset pipeline used by the short-drama service."""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

TRIPOSR_ROOT = Path("/Users/aoo/AI/Tools/TripoSR")
TRIPOSR_PYTHON = TRIPOSR_ROOT / ".venv/bin/python"
TRIPOSR_MODEL = Path("/Users/aoo/Code/AI Agent/models/3d/TripoSR")


def _run(command: list[str], *, cwd: Path, timeout: int) -> None:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout)[-1200:])


def reconstruct(source: Path, output: Path, *, resolution: int) -> Path:
    raw_root = output / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)
    _run(
        [
            str(TRIPOSR_PYTHON), str(TRIPOSR_ROOT / "run.py"), str(source),
            "--device", "mps", "--pretrained-model-name-or-path", str(TRIPOSR_MODEL),
            "--chunk-size", "4096", "--mc-resolution", str(resolution),
            "--foreground-ratio", "0.85", "--output-dir", str(raw_root),
            "--model-save-format", "glb",
        ],
        cwd=TRIPOSR_ROOT,
        timeout=1800,
    )
    mesh = raw_root / "0/mesh.glb"
    if not mesh.is_file() or mesh.stat().st_size < 1024:
        raise RuntimeError("TripoSR 未生成有效 GLB 网格")
    return mesh


def clean_and_render(raw_mesh: Path, output: Path, *, kind: str) -> dict:
    import bpy
    from mathutils import Vector

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(raw_mesh))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError("Blender 未读取到网格")
    bpy.context.view_layer.objects.active = meshes[0]
    for obj in meshes:
        obj.select_set(True)
    if len(meshes) > 1:
        bpy.ops.object.join()
    asset = bpy.context.view_layer.objects.active
    asset.name = "ShortDramaAsset"
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=0.0005)
    bpy.ops.mesh.delete_loose(use_verts=True, use_edges=True, use_faces=True)
    bpy.ops.mesh.fill_holes(sides=0)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    face_limit = {"character": 50_000, "prop": 20_000, "scene": 200_000}[kind]
    if len(asset.data.polygons) > face_limit:
        modifier = asset.modifiers.new("ConservativeDecimate", "DECIMATE")
        modifier.ratio = max(0.08, (face_limit * 0.95) / len(asset.data.polygons))
        modifier.use_collapse_triangulate = True
        bpy.context.view_layer.objects.active = asset
        bpy.ops.object.modifier_apply(modifier=modifier.name)

    import bmesh
    repair_mesh = bmesh.new(); repair_mesh.from_mesh(asset.data)
    # TripoSR can leave a microscopic duplicate sliver where one edge belongs
    # to three faces. Remove only the smallest surplus faces before sealing the
    # resulting boundary; this preserves the visible surface and UV layout.
    surplus_faces = set()
    for edge in repair_mesh.edges:
        if len(edge.link_faces) > 2:
            surplus_faces.update(sorted(edge.link_faces, key=lambda face: face.calc_area())[:len(edge.link_faces) - 2])
    if surplus_faces:
        bmesh.ops.delete(repair_mesh, geom=list(surplus_faces), context="FACES")
    boundary_edges = [edge for edge in repair_mesh.edges if edge.is_boundary]
    if boundary_edges:
        bmesh.ops.holes_fill(repair_mesh, edges=boundary_edges, sides=0)
    bmesh.ops.recalc_face_normals(repair_mesh, faces=list(repair_mesh.faces))
    repair_mesh.to_mesh(asset.data); repair_mesh.free(); asset.data.update()
    if len(asset.data.polygons) > face_limit:
        raise RuntimeError(f"网格审核失败：面数{len(asset.data.polygons)}超过上限{face_limit}")

    vertex_count = len(asset.data.vertices)
    face_count = len(asset.data.polygons)
    audit_mesh = bmesh.new(); audit_mesh.from_mesh(asset.data)
    non_manifold_edges = sum(1 for edge in audit_mesh.edges if not edge.is_manifold)
    loose_vertices = sum(1 for vertex in audit_mesh.verts if not vertex.link_edges)
    audit_mesh.free()
    uv_layers = len(asset.data.uv_layers)
    material_slots = len(asset.material_slots)
    if non_manifold_edges:
        raise RuntimeError(f"网格审核失败：仍有{non_manifold_edges}条非流形边")

    world_corners = [asset.matrix_world @ Vector(corner) for corner in asset.bound_box]
    minimum = Vector((min(v.x for v in world_corners), min(v.y for v in world_corners), min(v.z for v in world_corners)))
    maximum = Vector((max(v.x for v in world_corners), max(v.y for v in world_corners), max(v.z for v in world_corners)))
    center = (minimum + maximum) * 0.5
    extent = max(maximum.x - minimum.x, maximum.y - minimum.y, maximum.z - minimum.z, 0.001)
    asset.location -= center
    asset.location.z += (maximum.z - minimum.z) * 0.5

    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE"
        preview_engine = scene.render.engine
        scene.render.engine = "CYCLES"
        scene.cycles.samples = 64
        scene.cycles.use_denoising = True
        scene.cycles.device = "GPU"
    except Exception as error:
        raise RuntimeError(f"Cycles 64采样最终渲染不可用：{error}") from error
    scene.render.resolution_x = 928 if kind == "character" else 1920
    scene.render.resolution_y = 1664 if kind == "character" else 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.view_settings.look = "AgX - Medium High Contrast"
    bpy.context.view_layer.use_pass_z = True
    bpy.context.view_layer.use_pass_normal = True

    camera_data = bpy.data.cameras.new("AssetCamera")
    camera = bpy.data.objects.new("AssetCamera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = extent * 1.35

    def track(obj, target=Vector((0, 0, 0))):
        obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()

    key = bpy.data.lights.new("Key", "AREA")
    key.energy, key.shape, key.size = 900, "DISK", extent * 2
    key_obj = bpy.data.objects.new("Key", key)
    scene.collection.objects.link(key_obj)
    key_obj.location = (extent * 2, -extent * 2, extent * 2.5)
    track(key_obj)
    fill = bpy.data.lights.new("Fill", "AREA")
    fill.energy, fill.size = 450, extent * 2
    fill_obj = bpy.data.objects.new("Fill", fill)
    scene.collection.objects.link(fill_obj)
    fill_obj.location = (-extent * 2, -extent, extent)
    track(fill_obj)

    output.mkdir(parents=True, exist_ok=True)
    clean_mesh = output / "asset_clean.glb"
    blend_file = output / "asset_clean.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_file))
    asset.select_set(True)
    bpy.context.view_layer.objects.active = asset
    bpy.ops.export_scene.gltf(filepath=str(clean_mesh), export_format="GLB", use_selection=True)

    render_root = output / "renders"
    render_root.mkdir(exist_ok=True)
    radius = extent * 2.2
    def emission_material(name: str, mode: str):
        material = bpy.data.materials.new(name)
        material.use_nodes = True
        nodes = material.node_tree.nodes
        nodes.clear()
        output_node = nodes.new("ShaderNodeOutputMaterial")
        emission = nodes.new("ShaderNodeEmission")
        if mode == "normal":
            geometry = nodes.new("ShaderNodeNewGeometry")
            scale = nodes.new("ShaderNodeVectorMath"); scale.operation = "SCALE"; scale.inputs[3].default_value = 0.5
            add = nodes.new("ShaderNodeVectorMath"); add.operation = "ADD"; add.inputs[1].default_value = (0.5, 0.5, 0.5)
            material.node_tree.links.new(geometry.outputs["Normal"], scale.inputs[0])
            material.node_tree.links.new(scale.outputs[0], add.inputs[0])
            material.node_tree.links.new(add.outputs[0], emission.inputs["Color"])
        else:
            geometry = nodes.new("ShaderNodeNewGeometry")
            transform = nodes.new("ShaderNodeVectorTransform"); transform.vector_type = "POINT"; transform.convert_from = "WORLD"; transform.convert_to = "CAMERA"
            separate = nodes.new("ShaderNodeSeparateXYZ")
            negate = nodes.new("ShaderNodeMath"); negate.operation = "MULTIPLY"; negate.inputs[1].default_value = -1.0
            divide = nodes.new("ShaderNodeMath"); divide.operation = "DIVIDE"; divide.inputs[1].default_value = radius * 4
            material.node_tree.links.new(geometry.outputs["Position"], transform.inputs["Vector"])
            material.node_tree.links.new(transform.outputs["Vector"], separate.inputs[0])
            material.node_tree.links.new(separate.outputs["Z"], negate.inputs[0])
            material.node_tree.links.new(negate.outputs[0], divide.inputs[0])
            material.node_tree.links.new(divide.outputs[0], emission.inputs["Color"])
        material.node_tree.links.new(emission.outputs[0], output_node.inputs[0])
        return material
    depth_material = emission_material("DepthAudit", "depth")
    normal_material = emission_material("NormalAudit", "normal")
    angles = [("front_0", 0, 0), ("left_45", -45, 0), ("right_45", 45, 0),
              ("side_90", 90, 0), ("back_180", 180, 0), ("top", 0, 70), ("bottom", 0, -35)]
    rendered = []
    for label, degrees, elevation in angles:
        radians = math.radians(degrees)
        elevation_radians = math.radians(elevation)
        horizontal_radius = radius * math.cos(elevation_radians)
        camera.location = (math.sin(radians) * horizontal_radius, -math.cos(radians) * horizontal_radius,
                           extent * 0.5 + radius * math.sin(elevation_radians))
        track(camera)
        path = render_root / f"{label}.png"
        scene.render.filepath = str(path)
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.cycles.samples = 64
        bpy.ops.render.render(write_still=True)
        from PIL import Image
        rgba = Image.open(path).convert("RGBA")
        mask_path = render_root / f"{label}_mask.png"
        rgba.getchannel("A").save(mask_path)
        depth_path = render_root / f"{label}_depth.png"
        bpy.context.view_layer.material_override = depth_material
        scene.cycles.samples = 1
        scene.render.filepath = str(depth_path)
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "BW"
        bpy.ops.render.render(write_still=True)
        normal_path = render_root / f"{label}_normal.png"
        bpy.context.view_layer.material_override = normal_material
        scene.render.filepath = str(normal_path)
        scene.render.image_settings.color_mode = "RGBA"
        bpy.ops.render.render(write_still=True)
        bpy.context.view_layer.material_override = None
        rendered.append({"label": label, "angle": degrees, "elevation": elevation, "path": str(path), "mask_path": str(mask_path),
                         "depth_path": str(depth_path), "normal_path": str(normal_path), "channels": ["RGB", "Alpha/Mask", "Depth/Z", "Normal"]})

    # Produce a real Blender camera-source clip for the downstream H3 Ref2VA
    # workflow.  It is deliberately a neutral, deterministic orbit: H3 owns
    # identity/style rendering while Blender supplies geometry, camera motion
    # and occlusion only.
    bpy.context.view_layer.material_override = None
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 576 if kind == "character" else 1024
    scene.render.resolution_y = 1024 if kind == "character" else 576
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.frame_start = 1
    scene.frame_end = 96
    source_video = output / "blender_source.mp4"
    source_frames = output / ".blender_source_frames"
    if source_frames.exists():
        shutil.rmtree(source_frames)
    source_frames.mkdir(parents=True)
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("ShortDramaWorld")
    scene.world.color = (0.12, 0.12, 0.12)
    scene.render.filepath = str(source_frames / "source_")
    for frame in (1, 25, 49, 73, 96):
        radians = math.radians(-45 + (frame - 1) / 95 * 90)
        camera.location = (math.sin(radians) * radius, -math.cos(radians) * radius, extent * 0.55)
        track(camera)
        camera.keyframe_insert(data_path="location", frame=frame)
        camera.keyframe_insert(data_path="rotation_euler", frame=frame)
    action = camera.animation_data.action if camera.animation_data else None
    if action is not None and hasattr(action, "fcurves"):
        for curve in action.fcurves:
            for point in curve.keyframe_points:
                point.interpolation = "BEZIER"
    bpy.ops.render.render(animation=True)
    import imageio_ffmpeg
    encoded = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-framerate", "24", "-i", str(source_frames / "source_%04d.png"),
         "-frames:v", "96", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24", "-movflags", "+faststart", str(source_video)],
        capture_output=True, text=True, timeout=1800,
    )
    shutil.rmtree(source_frames, ignore_errors=True)
    if encoded.returncode:
        raise RuntimeError(f"Blender源视频编码失败：{encoded.stderr[-500:]}")
    if not source_video.is_file() or source_video.stat().st_size < 1024:
        raise RuntimeError("Blender 未生成有效H3源视频")

    report = {
        "workflow": "FLUX.2 Klein 9B -> TripoSR -> Blender headless",
        "kind": kind,
        "source_mesh": str(raw_mesh),
        "clean_mesh": str(clean_mesh),
        "blend_file": str(blend_file),
        "vertex_count": vertex_count,
        "face_count": face_count,
        "face_limit": face_limit,
        "coordinate_system": {"unit":"meter", "x":"right", "y":"up", "z":"toward_camera", "blender_axis_conversion":"business_y=blender_z,business_z=-blender_y"},
        "origin_policy": "asset_ground_center",
        "manifold_check": "automatic_geometry_cleanup_applied",
        "geometry_audit": {"non_manifold_edges":non_manifold_edges, "loose_vertices":loose_vertices,
                           "uv_layers":uv_layers, "material_slots":material_slots, "boundary_checked":True,
                           "unit_scale":scene.unit_settings.scale_length, "render_engine":scene.render.engine,
                           "preview_engine":preview_engine, "final_samples":64},
        "renders": rendered,
        "source_video": str(source_video),
        "source_video_spec": {"fps":24, "frames":96, "duration_seconds":4, "role":"geometry_camera_motion_only"},
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--kind", choices=("character", "prop", "scene"), required=True)
    parser.add_argument("--resolution", type=int, default=256)
    parser.add_argument("--mode", choices=("all", "reconstruct", "blender"), default="all")
    args = parser.parse_args()
    source, output = Path(args.source).resolve(), Path(args.output).resolve()
    if not source.is_file():
        raise SystemExit("3D 输入图不存在")
    started = time.time()
    raw_mesh = output / "raw/0/mesh.glb"
    if args.mode in {"all", "reconstruct"}:
        raw_mesh = reconstruct(source, output, resolution=max(128, min(320, args.resolution)))
    if args.mode == "reconstruct":
        print(json.dumps({"raw_mesh":str(raw_mesh), "elapsed_seconds":round(time.time() - started, 3)}, ensure_ascii=False))
        return
    if not raw_mesh.is_file():
        raise SystemExit("TripoSR原始GLB不存在")
    report = clean_and_render(raw_mesh, output, kind=args.kind)
    report["elapsed_seconds"] = round(time.time() - started, 3)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
