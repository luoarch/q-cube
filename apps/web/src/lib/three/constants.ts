export const CUBE_SIZE = 5;
export const HALF_CUBE = CUBE_SIZE / 2;

export const DEFAULT_CAMERA_POSITION: [number, number, number] = [8, 6, 8];
export const DEFAULT_CAMERA_TARGET: [number, number, number] = [0, 0, 0];

export const AXIS_LABELS = {
  x: 'Earnings Yield (Value)',
  y: 'Return on Capital (Profitability)',
  z: 'Quality Score',
} as const;

export const PARTICLE_SEGMENTS_HI = 32;
export const PARTICLE_SEGMENTS_LO = 8;
