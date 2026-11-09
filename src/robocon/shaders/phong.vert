#version 330 core

in vec3 in_position;
in vec3 in_normal;
in vec2 in_uv;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
// transpose(inverse(mat3(model))), computed once per object on the CPU
uniform mat3 u_normal_matrix;

out vec3 v_world_position;
out vec3 v_normal;
out vec2 v_uv;

void main() {
    vec4 world = u_model * vec4(in_position, 1.0);
    v_world_position = world.xyz;
    v_normal = u_normal_matrix * in_normal;
    v_uv = in_uv;
    gl_Position = u_projection * u_view * world;
}
