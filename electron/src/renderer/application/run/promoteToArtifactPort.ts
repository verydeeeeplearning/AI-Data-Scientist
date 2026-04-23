export type PromoteAudience = 'ds' | 'exec' | 'ml';

export const PROMOTE_AUDIENCES: readonly PromoteAudience[] = ['ds', 'exec', 'ml'];

export interface PromoteToArtifactInput {
  readonly runId: string;
  readonly cardId: string;
  readonly audience: PromoteAudience;
  readonly title?: string | null;
}

export interface PromoteToArtifactResult {
  readonly artifactId: string;
  readonly runId: string;
  readonly cardId: string;
  readonly audience: PromoteAudience;
  readonly title: string;
  readonly createdAt: number;
}

export interface PromoteToArtifactPort {
  (input: PromoteToArtifactInput): Promise<PromoteToArtifactResult>;
}
