export type RpcFn = (
  method: string,
  params?: Record<string, unknown>,
  options?: { timeoutMs?: number },
) => Promise<Record<string, unknown>>;

export type OrgRole = 'admin' | 'editor' | 'viewer';

export interface OrgMember {
  userId: string;
  role: OrgRole;
  displayName?: string | null;
  invitedAt: number;
}

export interface OrgSettings {
  allowedProviders: string[];
  maxBudgetUsdPerUser: number | null;
  maxBudgetUsdPerOrg: number | null;
  externalDataTransferAllowed: boolean;
  exportAllowed: boolean;
  connectorCreationAllowed: boolean;
}

export interface OrganizationSummary {
  id: string;
  name: string;
  members: OrgMember[];
  settings: OrgSettings;
  createdAt: number;
  updatedAt: number;
}

export interface UsageByActor {
  actorId: string;
  costUsd: number;
  runCount: number;
  providers: Record<string, number>;
}

export interface OrganizationUsage {
  totalCostUsd: number;
  totalRunCount: number;
  perUser: UsageByActor[];
}

export interface OrganizationSnapshot {
  organization: OrganizationSummary;
  usage: OrganizationUsage;
}

export interface SkillPermissions {
  network: string[];
  filesystem: string[];
}

export interface SkillSummary {
  name: string;
  description: string;
  category: string;
  tags: string[];
  token_estimate: number;
  version: string;
  author: string;
  enabled: boolean;
  sourceKind: string;
  sourcePath: string | null;
  tools: string[];
  permissions: SkillPermissions;
  content?: string;
  related_skills?: string[];
}
