declare module 'react-confetti' {
  import { ComponentType } from 'react';

  interface ConfettiProps {
    width?: number;
    height?: number;
    numberOfPieces?: number;
    recycle?: boolean;
    gravity?: number;
    wind?: number;
    friction?: number;
    opacity?: number;
    colors?: string[];
    initialVelocityX?: number;
    initialVelocityY?: number;
    confettiSource?: {
      x: number;
      y: number;
      w: number;
      h: number;
    };
    drawShape?: (context: CanvasRenderingContext2D) => void;
    onConfettiComplete?: (confetti: any) => void;
  }

  const Confetti: ComponentType<ConfettiProps>;
  export default Confetti;
} 