#version 330 core

// Blinn-Phong: ambient + diffuse + specular from one point light.

in vec3 v_world_position;
in vec3 v_normal;
in vec2 v_uv;

uniform sampler2D u_texture;
uniform bool u_has_texture;
uniform vec3 u_diffuse_color;   // material colour, used when there is no texture
uniform float u_shininess;

uniform vec3 u_light_position;
uniform vec3 u_light_color;
uniform vec3 u_view_position;
uniform float u_ambient;
uniform float u_specular_strength;

out vec4 frag_color;

void main() {
    vec3 albedo = u_has_texture ? texture(u_texture, v_uv).rgb : u_diffuse_color;

    vec3 normal = normalize(v_normal);
    if (!gl_FrontFacing) {
        normal = -normal;  // Blender exports are not consistently wound; light both sides.
    }
    vec3 to_light = normalize(u_light_position - v_world_position);
    vec3 to_viewer = normalize(u_view_position - v_world_position);

    float diffuse = max(dot(normal, to_light), 0.0);
    vec3 halfway = normalize(to_light + to_viewer);
    float specular = diffuse > 0.0 ? pow(max(dot(normal, halfway), 0.0), u_shininess) : 0.0;

    vec3 color = (u_ambient + diffuse) * albedo * u_light_color
               + u_specular_strength * specular * u_light_color;
    frag_color = vec4(color, 1.0);
}
