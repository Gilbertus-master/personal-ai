'use client';

import { useRef, useEffect, useCallback } from 'react';
import { cn } from '../../lib/utils';

export interface VoiceWaveformProps {
  analyserNode: AnalyserNode | null;
  isActive: boolean;
  width?: number;
  height?: number;
  barColor?: string;
  className?: string;
}

export function VoiceWaveform({
  analyserNode,
  isActive,
  width = 200,
  height = 48,
  barColor = 'var(--accent)',
  className,
}: VoiceWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = width * dpr;
    const h = height * dpr;

    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }

    ctx.clearRect(0, 0, w, h);

    const barWidth = 3 * dpr;
    const gap = 1 * dpr;
    const barCount = Math.floor(w / (barWidth + gap));

    if (!analyserNode || !isActive) {
      // Draw static flat bars
      ctx.fillStyle = barColor;
      for (let i = 0; i < barCount; i++) {
        const x = i * (barWidth + gap);
        const barH = 2 * dpr;
        const y = (h - barH) / 2;
        ctx.fillRect(x, y, barWidth, barH);
      }
      return;
    }

    const dataArray = new Uint8Array(analyserNode.frequencyBinCount);
    analyserNode.getByteFrequencyData(dataArray);

    ctx.fillStyle = barColor;
    const step = Math.max(1, Math.floor(dataArray.length / barCount));

    for (let i = 0; i < barCount; i++) {
      const value = dataArray[i * step] ?? 0;
      const barH = Math.max(2 * dpr, (value / 255) * h * 0.9);
      const x = i * (barWidth + gap);
      const y = (h - barH) / 2;
      ctx.fillRect(x, y, barWidth, barH);
    }

    rafRef.current = requestAnimationFrame(draw);
  }, [analyserNode, isActive, width, height, barColor]);

  useEffect(() => {
    if (isActive && analyserNode) {
      rafRef.current = requestAnimationFrame(draw);
    } else {
      // Draw static state once
      draw();
    }

    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [isActive, analyserNode, draw]);

  return (
    <canvas
      ref={canvasRef}
      className={cn('block', className)}
      style={{ width, height }}
    />
  );
}
