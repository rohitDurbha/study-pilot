'use client';

import React, { useEffect, useState, useCallback } from 'react';
import ReactFlow, {
  ReactFlowProvider,
  Controls,
  Background,
  Node,
  Edge,
  useNodesState,
  useEdgesState,
} from 'reactflow';
import dagre from 'dagre';
import 'reactflow/dist/style.css';

interface MindmapNode {
  title: string;
  children?: MindmapNode[];
}

interface MindmapContentProps {
  data: {
    title: string;
    root: MindmapNode;
  };
}

let nodeCounter = 0;

const colors = [
  { bg: '#3b82f6', border: '#2563eb' }, // blue - root
  { bg: '#6366f1', border: '#4f46e5' }, // indigo
  { bg: '#8b5cf6', border: '#7c3aed' }, // violet
  { bg: '#a855f7', border: '#9333ea' }, // purple
  { bg: '#d946ef', border: '#c026d3' }, // fuchsia
];

function getColor(depth: number) {
  return colors[Math.min(depth, colors.length - 1)];
}

/**
 * If a node has leaf children (no grandchildren), collapse them into
 * a single node with bullet points instead of separate boxes.
 */
function flattenTree(
  node: MindmapNode,
  parentId: string | null,
  nodes: Node[],
  edges: Edge[],
  depth: number = 0
) {
  const id = `node-${nodeCounter++}`;
  const color = getColor(depth);

  // Check if this node's children are all leaves (no grandchildren)
  const children = node.children || [];
  const allChildrenAreLeaves = children.length > 0 &&
    children.every(c => !c.children || c.children.length === 0);

  if (allChildrenAreLeaves && children.length >= 2) {
    // Collapse: show parent title + children as bullet list in one box
    const bulletList = children.map(c => c.title).join('\n• ');
    const label = `${node.title}\n\n• ${bulletList}`;

    nodes.push({
      id,
      data: { label },
      position: { x: 0, y: 0 },
      style: {
        background: color.bg,
        color: '#ffffff',
        border: `2px solid ${color.border}`,
        borderRadius: '10px',
        padding: '10px 14px',
        fontSize: '11px',
        fontWeight: '500',
        whiteSpace: 'pre-line' as any,
        textAlign: 'left' as any,
        lineHeight: '1.5',
        maxWidth: '220px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
      },
    });
  } else {
    // Regular node
    const isRoot = depth === 0;
    nodes.push({
      id,
      data: { label: node.title },
      position: { x: 0, y: 0 },
      style: {
        background: color.bg,
        color: '#ffffff',
        border: `2px solid ${color.border}`,
        borderRadius: isRoot ? '12px' : '8px',
        padding: isRoot ? '10px 20px' : '6px 14px',
        fontSize: isRoot ? '14px' : '12px',
        fontWeight: isRoot ? '700' : '500',
        maxWidth: '180px',
        textAlign: 'center' as any,
        boxShadow: '0 2px 6px rgba(0,0,0,0.12)',
      },
    });

    // Recurse into children that have their own children
    children.forEach((child) =>
      flattenTree(child, id, nodes, edges, depth + 1)
    );
  }

  if (parentId) {
    edges.push({
      id: `${parentId}-${id}`,
      source: parentId,
      target: id,
      type: 'smoothstep',
      style: { stroke: '#64748b', strokeWidth: 2 },
    });
  }
}

const nodeWidth = 190;
const nodeHeight = 50;

function applyLayout(nodes: Node[], edges: Edge[]) {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'TB', nodesep: 30, ranksep: 60 });

  nodes.forEach((n) =>
    g.setNode(n.id, { width: nodeWidth, height: nodeHeight })
  );
  edges.forEach((e) =>
    g.setEdge(e.source, e.target)
  );

  dagre.layout(g);

  return nodes.map((n) => {
    const pos = g.node(n.id);
    return {
      ...n,
      position: { x: pos.x - nodeWidth / 2, y: pos.y - nodeHeight / 2 },
    };
  });
}

function MindmapFlow({ data }: MindmapContentProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    nodeCounter = 0;
    const n: Node[] = [];
    const e: Edge[] = [];
    flattenTree(data.root, null, n, e);
    setNodes(applyLayout(n, e));
    setEdges(e);
  }, [data]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      nodesDraggable={true}
      nodesConnectable={false}
      zoomOnScroll
      panOnScroll
      fitView
      fitViewOptions={{ padding: 0.2 }}
      minZoom={0.3}
      maxZoom={1.5}
    >
      <Background color="#475569" gap={24} size={1} />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}

export default function MindmapContent({ data }: MindmapContentProps) {
  if (!data || !data.root?.title) {
    return (
      <div className="w-full p-8 text-center text-gray-400">
        No mindmap data available
      </div>
    );
  }

  return (
    <div className="w-full h-[75vh]">
      <ReactFlowProvider>
        <MindmapFlow data={data} />
      </ReactFlowProvider>
    </div>
  );
}
