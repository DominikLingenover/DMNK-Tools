# lists with different variations of texture type
global names
names = []
# diffuse/
global diff_names
diff_names = dict.fromkeys(["diffuse", "diff", "albedo", "color", "col", "alb", "dif", "basecolor"], [0, 59, "diffuse"])
names.append(diff_names)
# ao/cavity
global ao_names
ao_names = dict.fromkeys(["ao", "ambientocclusion", "ambient_occlusion", "cavity"], [1, 58, "ao"])
names.append(ao_names)
# normal
global nml_names
nml_names = dict.fromkeys(["normal", "nrm", "nrml", "n", "norm_ogl", "normalbump"], [49, 57, "normal"])
names.append(nml_names)
# bump
global bump_names
bump_names = dict.fromkeys(["bump", "bmp", "height", "h"], [49, 57, "bump"])
names.append(bump_names)
# displacement
global disp_names
disp_names = dict.fromkeys(["displacement", "displace", "disp"], [70, 56, "disp"])
names.append(disp_names)
# roughness
global rough_names
rough_names = dict.fromkeys(["roughness", "rough", "r"], [7, 55, "rough"])
names.append(rough_names)
# glossiness
global gloss_names
gloss_names = dict.fromkeys(["gloss", "g", "glossiness"], [7, 55, "gloss"])
names.append(gloss_names)
# metalness
global metal_names
metal_names = dict.fromkeys(["metal", "metalness", "m", "metallic"], [14, 54, "metal"])
names.append(metal_names)
# specular
global spec_names
spec_names = dict.fromkeys(["specular", "spec", "s", "refl", "reflectivity"], [5, 54, "spec"])
names.append(spec_names)
# transparency
global opc_names
opc_names = dict.fromkeys(["transparency", "t", "opacity", "o"], [47, 53, "opacity"])
names.append(opc_names)
# emission
global emit_names
emit_names = dict.fromkeys(["emission", "emissive"], [48, 60, "emission"])
names.append(emit_names)
# file extensions
global extensions
extensions = (".jpg", ".exr", ".tex", ".tga", ".png", "tif", ".hdr")

# Creates a string from all names from above to use for regex
regex_names = ""
for imageType in names:
    for typeNames in imageType.keys():
        regex_names += typeNames + "|"
regex_names = regex_names[:-1]