import bpy
import mathutils
from typing import Optional, List, Iterable, Tuple, Any, Dict

bl_info = {
    "name": "Armature Proxy Mesh",
    "author": "Yuki Koyama",
    "version": (1, 0),
    "blender": (3, 3, 0),
    "location": "3D View",
    "description": "Easy creation of proxy meshes for a selected armature object.",
    "warning": "",
    "support": "TESTING",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Add Mesh"
}


# This function is from
# https://github.com/yuki-koyama/blender-cli-rendering
def set_smooth_shading(mesh: bpy.types.Mesh) -> None:
    for polygon in mesh.polygons:
        polygon.use_smooth = True


# This function is from
# https://github.com/yuki-koyama/blender-cli-rendering
def create_mesh_from_pydata(scene: bpy.types.Scene,
                            vertices: Iterable[Iterable[float]],
                            faces: Iterable[Iterable[int]],
                            mesh_name: str,
                            object_name: str,
                            use_smooth: bool = True) -> bpy.types.Object:
    # Add a new mesh and set vertices and faces
    # Note: In this case, it does not require to set edges.
    # Note: After manipulating mesh data, update() needs to be called.
    new_mesh: bpy.types.Mesh = bpy.data.meshes.new(mesh_name)
    new_mesh.from_pydata(vertices, [], faces)
    new_mesh.update()
    if use_smooth:
        set_smooth_shading(new_mesh)

    new_object: bpy.types.Object = bpy.data.objects.new(object_name, new_mesh)
    scene.collection.objects.link(new_object)

    return new_object


# This function is from
# https://github.com/yuki-koyama/blender-cli-rendering
def add_subdivision_surface_modifier(mesh_object: bpy.types.Object, level: int, is_simple: bool = False) -> None:
    '''
    https://docs.blender.org/api/current/bpy.types.SubsurfModifier.html
    '''

    modifier: bpy.types.SubsurfModifier = mesh_object.modifiers.new(name="Subsurf", type='SUBSURF')

    modifier.levels = level
    modifier.render_levels = level
    modifier.subdivision_type = 'SIMPLE' if is_simple else 'CATMULL_CLARK'


# This function is from
# https://github.com/yuki-koyama/blender-cli-rendering
def create_armature_mesh(scene: bpy.types.Scene, armature_object: bpy.types.Object, mesh_name: str) -> bpy.types.Object:
    assert armature_object.type == 'ARMATURE', 'Error'
    assert len(armature_object.data.bones) != 0, 'Error'

    def add_rigid_vertex_group(target_object: bpy.types.Object, name: str, vertex_indices: Iterable[int]) -> None:
        new_vertex_group = target_object.vertex_groups.new(name=name)
        for vertex_index in vertex_indices:
            new_vertex_group.add([vertex_index], 1.0, 'REPLACE')

    def generate_bone_mesh_pydata(radius: float, length: float) -> Tuple[List[mathutils.Vector], List[List[int]]]:
        base_radius = radius
        top_radius = 0.5 * radius

        vertices = [
            # Cross section of the base part
            mathutils.Vector((-base_radius, 0.0, +base_radius)),
            mathutils.Vector((+base_radius, 0.0, +base_radius)),
            mathutils.Vector((+base_radius, 0.0, -base_radius)),
            mathutils.Vector((-base_radius, 0.0, -base_radius)),

            # Cross section of the top part
            mathutils.Vector((-top_radius, length, +top_radius)),
            mathutils.Vector((+top_radius, length, +top_radius)),
            mathutils.Vector((+top_radius, length, -top_radius)),
            mathutils.Vector((-top_radius, length, -top_radius)),

            # End points
            mathutils.Vector((0.0, -base_radius, 0.0)),
            mathutils.Vector((0.0, length + top_radius, 0.0))
        ]

        faces = [
            # End point for the base part
            [8, 1, 0],
            [8, 2, 1],
            [8, 3, 2],
            [8, 0, 3],

            # End point for the top part
            [9, 4, 5],
            [9, 5, 6],
            [9, 6, 7],
            [9, 7, 4],

            # Side faces
            [0, 1, 5, 4],
            [1, 2, 6, 5],
            [2, 3, 7, 6],
            [3, 0, 4, 7],
        ]

        return vertices, faces

    armature_data: bpy.types.Armature = armature_object.data

    vertices: List[mathutils.Vector] = []
    faces: List[List[int]] = []
    vertex_groups: List[Dict[str, Any]] = []

    for bone in armature_data.bones:
        radius = 0.10 * (0.10 + bone.length)
        temp_vertices, temp_faces = generate_bone_mesh_pydata(radius, bone.length)

        vertex_index_offset = len(vertices)

        temp_vertex_group = {'name': bone.name, 'vertex_indices': []}
        for local_index, vertex in enumerate(temp_vertices):
            vertices.append(bone.matrix_local @ vertex)
            temp_vertex_group['vertex_indices'].append(local_index + vertex_index_offset)
        vertex_groups.append(temp_vertex_group)

        for face in temp_faces:
            if len(face) == 3:
                faces.append([
                    face[0] + vertex_index_offset,
                    face[1] + vertex_index_offset,
                    face[2] + vertex_index_offset,
                ])
            else:
                faces.append([
                    face[0] + vertex_index_offset,
                    face[1] + vertex_index_offset,
                    face[2] + vertex_index_offset,
                    face[3] + vertex_index_offset,
                ])

    new_object = create_mesh_from_pydata(scene, vertices, faces, mesh_name, mesh_name)
    new_object.matrix_world = armature_object.matrix_world

    for vertex_group in vertex_groups:
        add_rigid_vertex_group(new_object, vertex_group['name'], vertex_group['vertex_indices'])

    armature_modifier = new_object.modifiers.new('Armature', 'ARMATURE')
    armature_modifier.object = armature_object
    armature_modifier.use_vertex_groups = True

    add_subdivision_surface_modifier(new_object, 1, is_simple=True)
    add_subdivision_surface_modifier(new_object, 2, is_simple=False)

    # Set the armature as the parent of the new object
    bpy.ops.object.select_all(action='DESELECT')
    new_object.select_set(True)
    armature_object.select_set(True)
    bpy.context.view_layer.objects.active = armature_object
    bpy.ops.object.parent_set(type='OBJECT')

    return new_object


class APM_OP_AddMesh(bpy.types.Operator):

    bl_idname = "amp.add_mesh"
    bl_label = "Add mesh"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}

    def __init__(self) -> None:
        super().__init__()

    def execute(self, context: bpy.types.Context):
        name = bpy.context.object.name + "_proxy"
        create_armature_mesh(bpy.context.scene, bpy.context.object, name)

        return {'FINISHED'}


class AMP_PT_ControlPanel(bpy.types.Panel):

    bl_label = "Armature Proxy Mesh"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "APM"

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return True

    def draw_header(self, context: bpy.types.Context):
        layout = self.layout
        layout.label(text="", icon='PLUGIN')

    def draw(self, context: bpy.types.Context):
        layout = self.layout

        ops: List[bpy.type.Operator] = [
            APM_OP_AddMesh
        ]

        for op in ops:
            layout.operator(op.bl_idname, text=op.bl_label)


classes = [
    APM_OP_AddMesh,
    AMP_PT_ControlPanel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
