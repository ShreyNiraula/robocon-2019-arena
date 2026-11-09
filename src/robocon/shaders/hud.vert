#version 330 core

in vec2 in_corner;  // (0,0) bottom-left .. (1,1) top-right

uniform vec4 u_rect;  // clip-space left, bottom, width, height

out vec2 v_uv;

void main() {
    v_uv = in_corner;
    gl_Position = vec4(u_rect.xy + in_corner * u_rect.zw, 0.0, 1.0);
}
