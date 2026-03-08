uniform float uTime;
uniform vec3 uColor;
varying vec3 vNormal;
varying vec3 vPosition;

void main() {
  // Fresnel-like glow effect
  float intensity = pow(0.7 - dot(vNormal, vec3(0.0, 0.0, 1.0)), 2.0);

  // Time-modulated emission
  float pulse = 0.5 + 0.5 * sin(uTime * 3.0);
  float emission = mix(1.0, 2.0, pulse);

  gl_FragColor = vec4(uColor * intensity * emission, intensity * 0.8);
}
