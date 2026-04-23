import type { Meta, StoryObj } from '@storybook/react';
import { AlertTriangle, ArrowUpRight, ShieldCheck } from 'lucide-react';
import { Badge, Button } from '../primitives';
import {
  DrawerSurface,
  DrawerSurfaceBody,
  DrawerSurfaceEyebrow,
  DrawerSurfaceHeader,
  DrawerSurfaceSection,
  DrawerSurfaceSectionTitle,
  DrawerSurfaceStat,
  DrawerSurfaceStatGrid,
} from './DrawerSurface';

type DrawerSurfaceDemoProps = {
  readonly eyebrow: string;
  readonly title: string;
  readonly description: string;
  readonly statusTone: 'success' | 'warning' | 'danger';
  readonly statusLabel: string;
  readonly bodyClassName?: string;
};

function DrawerSurfaceDemo({
  eyebrow,
  title,
  description,
  statusTone,
  statusLabel,
  bodyClassName,
}: DrawerSurfaceDemoProps) {
  return (
    <div className="min-h-screen bg-ds-bg p-ds-6">
      <DrawerSurface className="mx-auto max-w-3xl rounded-ds-xl border">
        <DrawerSurfaceHeader>
          <div className="min-w-0 flex-1 space-y-ds-2">
            <DrawerSurfaceEyebrow>{eyebrow}</DrawerSurfaceEyebrow>
            <div className="flex flex-wrap items-start justify-between gap-ds-3">
              <div className="min-w-0 space-y-ds-2">
                <h2 className="text-ds-xl font-semibold text-ds-text">{title}</h2>
                <p className="max-w-2xl text-ds-sm leading-6 text-ds-muted">{description}</p>
              </div>
              <Badge tone={statusTone} compact className="normal-case">
                {statusLabel}
              </Badge>
            </div>
          </div>
        </DrawerSurfaceHeader>

        <DrawerSurfaceBody className={bodyClassName}>
          <DrawerSurfaceStatGrid>
            <DrawerSurfaceStat label="Run" value="run-2026-04-20-017" />
            <DrawerSurfaceStat label="Owner" value="autonomous-runtime" />
            <DrawerSurfaceStat label="Stage" value="verification" />
            <DrawerSurfaceStat label="Latency" value="1.24s" />
          </DrawerSurfaceStatGrid>

          <DrawerSurfaceSection>
            <DrawerSurfaceSectionTitle>Summary</DrawerSurfaceSectionTitle>
            <p className="mt-ds-3 text-ds-sm leading-6 text-ds-text">
              This drawer surface is intended for inspector-style flows where the header, stat
              grid, and structured sections must stay visually consistent across runtime consoles.
            </p>
          </DrawerSurfaceSection>

          <DrawerSurfaceSection>
            <DrawerSurfaceSectionTitle>Suggested Actions</DrawerSurfaceSectionTitle>
            <div className="mt-ds-3 flex flex-wrap gap-ds-2">
              <Button size="sm" variant="primary" leadingIcon={<ShieldCheck size={14} aria-hidden="true" />}>
                Approve next step
              </Button>
              <Button size="sm" variant="secondary" leadingIcon={<ArrowUpRight size={14} aria-hidden="true" />}>
                Open evidence
              </Button>
              <Button size="sm" variant="danger" leadingIcon={<AlertTriangle size={14} aria-hidden="true" />}>
                Freeze writes
              </Button>
            </div>
          </DrawerSurfaceSection>
        </DrawerSurfaceBody>
      </DrawerSurface>
    </div>
  );
}

const meta = {
  title: 'Design System/Composites/DrawerSurface',
  component: DrawerSurface,
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component:
          'Inspector-style drawer composite for runtime and operator side panels. Use it when a surface needs shared header, stat-grid, and section chrome rather than a raw modal shell.',
      },
    },
  },
} satisfies Meta<typeof DrawerSurface>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  render: () => (
    <DrawerSurfaceDemo
      eyebrow="Runtime inspector"
      title="Run Detail Console"
      description="Shared drawer chrome for side-panel workflows, status summaries, and structured task follow-through."
      statusTone="success"
      statusLabel="Healthy"
    />
  ),
};

export const IncidentMode: Story = {
  render: () => (
    <DrawerSurfaceDemo
      eyebrow="Operator override"
      title="Incident Review Surface"
      description="Use the same drawer shell for escalated runtime events that need stronger visual urgency and action affordances."
      statusTone="warning"
      statusLabel="Attention needed"
      bodyClassName="bg-ds-warning/5"
    />
  ),
};
