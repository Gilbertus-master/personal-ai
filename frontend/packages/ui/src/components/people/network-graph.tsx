'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import type { NetworkGraph as NetworkGraphType } from '@gilbertus/api-client';
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  type SimulationNodeDatum,
  type SimulationLinkDatum,
} from 'd3-force';

interface NetworkGraphProps {
  data?: NetworkGraphType;
  isLoading?: boolean;
  onNodeClick?: (slug: string) => void;
}

interface GraphNode extends SimulationNodeDatum {
  id: string;
  name: string;
  role: string | null;
  org: string | null;
  event_count: number;
  radius: number;
  color: string;
}

interface GraphLink extends SimulationLinkDatum<GraphNode> {
  weight: number;
}

function orgToColor(org: string | null): string {
  if (!org) return '#6366f1';
  let hash = 0;
  for (let i = 0; i < org.length; i++) {
    hash = org.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = ((hash % 360) + 360) % 360;
  return `hsl(${hue}, 55%, 55%)`;
}

function nodeRadius(eventCount: number, maxCount: number): number {
  if (maxCount <= 0) return 8;
  return 5 + (eventCount / maxCount) * 25;
}

function linkWidth(weight: number, maxWeight: number): number {
  if (maxWeight <= 0) return 1;
  return 1 + (weight / maxWeight) * 5;
}

interface Tooltip {
  x: number;
  y: number;
  node: GraphNode;
}

export function NetworkGraph({ data, isLoading = false, onNodeClick }: NetworkGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [links, setLinks] = useState<GraphLink[]>([]);
  const [tooltip, setTooltip] = useState<Tooltip | null>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 560 });
  const [dragNode, setDragNode] = useState<GraphNode | null>(null);
  const [viewBox, setViewBox] = useState({ x: 0, y: 0, scale: 1 });
  const simulationRef = useRef<ReturnType<typeof forceSimulation<GraphNode>> | null>(null);

  // Measure container
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const obs = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) setDimensions({ width, height });
    });
    obs.observe(container);
    return () => obs.disconnect();
  }, []);

  // Build simulation
  useEffect(() => {
    if (!data?.nodes?.length) {
      setNodes([]);
      setLinks([]);
      return;
    }

    const maxCount = Math.max(...data.nodes.map((n) => n.event_count), 1);
    const maxWeight = Math.max(...data.edges.map((e) => e.weight), 1);

    const graphNodes: GraphNode[] = data.nodes.map((n) => ({
      id: n.id,
      name: n.name,
      role: n.role,
      org: n.org,
      event_count: n.event_count,
      radius: nodeRadius(n.event_count, maxCount),
      color: orgToColor(n.org),
    }));

    const nodeMap = new Map(graphNodes.map((n) => [n.id, n]));

    const graphLinks: GraphLink[] = data.edges
      .filter((e) => nodeMap.has(e.source) && nodeMap.has(e.target))
      .map((e) => ({
        source: e.source,
        target: e.target,
        weight: e.weight,
      }));

    const sim = forceSimulation<GraphNode>(graphNodes)
      .force(
        'link',
        forceLink<GraphNode, GraphLink>(graphLinks)
          .id((d) => d.id)
          .distance(100)
      )
      .force('charge', forceManyBody().strength(-200))
      .force('center', forceCenter(dimensions.width / 2, dimensions.height / 2))
      .force(
        'collide',
        forceCollide<GraphNode>().radius((d) => d.radius + 4)
      );

    simulationRef.current = sim;

    sim.on('tick', () => {
      setNodes([...graphNodes]);
      setLinks(
        graphLinks.map((l) => ({
          ...l,
          source: l.source as unknown as GraphNode,
          target: l.target as unknown as GraphNode,
        }))
      );
    });

    return () => {
      sim.stop();
    };
  }, [data, dimensions.width, dimensions.height]);

  // Mouse events for drag
  const handleMouseDown = useCallback(
    (e: React.MouseEvent, node: GraphNode) => {
      e.preventDefault();
      setDragNode(node);
      const sim = simulationRef.current;
      if (sim) {
        sim.alphaTarget(0.3).restart();
        node.fx = node.x;
        node.fy = node.y;
      }
    },
    []
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!dragNode || !svgRef.current) return;
      const svg = svgRef.current;
      const rect = svg.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * dimensions.width * viewBox.scale + viewBox.x;
      const y = ((e.clientY - rect.top) / rect.height) * dimensions.height * viewBox.scale + viewBox.y;
      dragNode.fx = x;
      dragNode.fy = y;
    },
    [dragNode, dimensions, viewBox]
  );

  const handleMouseUp = useCallback(() => {
    if (!dragNode) return;
    const sim = simulationRef.current;
    if (sim) sim.alphaTarget(0);
    dragNode.fx = null;
    dragNode.fy = null;
    setDragNode(null);
  }, [dragNode]);

  // Zoom
  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      const factor = e.deltaY > 0 ? 1.1 : 0.9;
      setViewBox((prev) => {
        const newScale = Math.min(Math.max(prev.scale * factor, 0.3), 3);
        return { ...prev, scale: newScale };
      });
    },
    []
  );

  if (isLoading) {
    return (
      <div
        className="flex h-full w-full items-center justify-center"
        style={{ backgroundColor: 'var(--surface)' }}
      >
        <div
          className="h-8 w-8 animate-spin rounded-full border-2 border-t-transparent"
          style={{ borderColor: 'var(--border)', borderTopColor: 'transparent' }}
        />
      </div>
    );
  }

  if (!data?.nodes?.length) {
    return (
      <div
        className="flex h-full w-full items-center justify-center text-sm"
        style={{ color: 'var(--text-secondary)' }}
      >
        Brak danych o sieci komunikacji
      </div>
    );
  }

  const maxWeight = Math.max(...data.edges.map((e) => e.weight), 1);

  const vbX = viewBox.x;
  const vbY = viewBox.y;
  const vbW = dimensions.width * viewBox.scale;
  const vbH = dimensions.height * viewBox.scale;

  return (
    <div ref={containerRef} className="relative h-full w-full">
      <svg
        ref={svgRef}
        width="100%"
        height="100%"
        viewBox={`${vbX} ${vbY} ${vbW} ${vbH}`}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        style={{ cursor: dragNode ? 'grabbing' : 'default' }}
      >
        {/* Edges */}
        {links.map((link, i) => {
          const source = link.source as GraphNode;
          const target = link.target as GraphNode;
          if (source.x == null || target.x == null) return null;
          const w = linkWidth(link.weight, maxWeight);
          const opacity = 0.2 + (link.weight / maxWeight) * 0.5;
          return (
            <line
              key={`link-${i}`}
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
              stroke="var(--border)"
              strokeWidth={w}
              strokeOpacity={opacity}
            />
          );
        })}

        {/* Nodes */}
        {nodes.map((node) => {
          if (node.x == null || node.y == null) return null;
          const showLabel = node.event_count > (data.nodes.length > 20 ? 10 : 3);
          return (
            <g
              key={node.id}
              style={{ cursor: 'pointer' }}
              onMouseDown={(e) => handleMouseDown(e, node)}
              onClick={() => onNodeClick?.(node.id)}
              onMouseEnter={(e) => {
                const rect = svgRef.current?.getBoundingClientRect();
                if (rect) {
                  setTooltip({
                    x: e.clientX - rect.left,
                    y: e.clientY - rect.top,
                    node,
                  });
                }
              }}
              onMouseLeave={() => setTooltip(null)}
            >
              <circle
                cx={node.x}
                cy={node.y}
                r={node.radius}
                fill={node.color}
                fillOpacity={0.85}
                stroke={node.color}
                strokeWidth={2}
                strokeOpacity={0.4}
              />
              {showLabel && (
                <text
                  x={node.x}
                  y={node.y! + node.radius + 14}
                  textAnchor="middle"
                  fontSize={11}
                  fill="var(--text-secondary)"
                  style={{ pointerEvents: 'none', userSelect: 'none' }}
                >
                  {node.name}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="pointer-events-none absolute z-10 rounded-lg px-3 py-2 text-sm shadow-lg"
          style={{
            left: tooltip.x + 12,
            top: tooltip.y - 10,
            backgroundColor: 'var(--surface)',
            border: '1px solid var(--border)',
            color: 'var(--text)',
          }}
        >
          <p className="font-medium">{tooltip.node.name}</p>
          {tooltip.node.role && (
            <p style={{ color: 'var(--text-secondary)' }}>{tooltip.node.role}</p>
          )}
          {tooltip.node.org && (
            <p style={{ color: 'var(--text-secondary)' }}>{tooltip.node.org}</p>
          )}
          <p style={{ color: 'var(--text-muted)' }}>
            Aktywność: {tooltip.node.event_count}
          </p>
        </div>
      )}
    </div>
  );
}
