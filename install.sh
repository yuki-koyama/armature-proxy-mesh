# Remove an existing zip file if any (optional)
rm -f armature_proxy_mesh.zip

# Remove unnecessary files
find . -name ".DS_Store" | xargs rm
find . -name "*.blend1" | xargs rm

# Create a package
zip -o armature_proxy_mesh.zip -ur armature_proxy_mesh

# Install the package to the blender
blender --background --python-expr "import bpy; bpy.ops.preferences.addon_install(overwrite=True, filepath=\"./armature_proxy_mesh.zip\")"
