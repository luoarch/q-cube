uniform float uTime;
varying vec3 vNormal;
varying vec3 vPosition;

void main() {
  vNormal = normalize(normalMatrix * normal);
  vPosition = position;

  // Subtle vertex displacement based on time
  float displacement = sin(uTime * 2.0 + position.y * 3.0) * 0.02;
  vec3 displaced = position + normal * displacement;

  gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
}
